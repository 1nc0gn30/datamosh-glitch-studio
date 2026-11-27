"""Security, XSS, DoS bounds, and HTTP hardening regression tests for Datamosh Glitch Studio v2.6.0."""
from __future__ import annotations

import base64
import http.client
import json
import struct
import threading
import time
import urllib.parse

import pytest

from datamosh_glitch_studio.bitplane_glitch import BitplaneGlitchEngine
from datamosh_glitch_studio.frame_io import ImageFrame, export_frame_sequence_html
from datamosh_glitch_studio.motion_vector_engine import MotionVectorEngine
from datamosh_glitch_studio.ui_server import MAX_BODY_BYTES, run_ui_server


@pytest.fixture(scope="module")
def hardened_server():
    server = run_ui_server(host="127.0.0.1", port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.08)
    yield port
    server.shutdown()
    server.server_close()


def _raw_request(port: int, method: str, path: str, headers: dict | None = None, body: bytes | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    hdrs = dict(headers or {})
    if "Host" not in hdrs:
        hdrs["Host"] = f"127.0.0.1:{port}"
    try:
        conn.request(method, path, body=body, headers=hdrs)
    except (BrokenPipeError, ConnectionResetError):
        # Server may legitimately emit 413 immediately upon checking Content-Length
        # and close the socket before the client finishes streaming >1 MiB.
        pass
    resp = conn.getresponse()
    raw = resp.read()
    resp_headers = {k.lower(): v for k, v in resp.getheaders()}
    status = resp.status
    conn.close()
    return status, resp_headers, raw


def _assert_security_headers(headers: dict):
    assert headers.get("x-frame-options") == "SAMEORIGIN"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    csp = headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'self' http://127.0.0.1:* http://localhost:*" in csp
    assert headers.get("vary") == "Origin"


def test_host_dns_rebinding_blocked(hardened_server):
    status, hdrs, body = _raw_request(hardened_server, "GET", "/health", headers={"Host": "evil.example.invalid"})
    assert status == 403
    _assert_security_headers(hdrs)
    assert "error" in json.loads(body.decode("utf-8"))


def test_cors_exact_port_and_untrusted_origin_blocking(hardened_server):
    # Port-suffix spoof (:80810) blocked on POST and OPTIONS
    for bad_origin in (f"http://127.0.0.1:{hardened_server}0", "http://127.0.0.1:8080", "https://evil.example.invalid"):
        st_opt, h_opt, b_opt = _raw_request(hardened_server, "OPTIONS", "/api/mosh", headers={"Origin": bad_origin})
        assert st_opt == 403
        _assert_security_headers(h_opt)
        assert "access-control-allow-origin" not in h_opt
        assert "error" in json.loads(b_opt.decode("utf-8"))

        st_post, h_post, b_post = _raw_request(
            hardened_server,
            "POST",
            "/api/mosh",
            headers={"Origin": bad_origin, "Content-Type": "application/json"},
            body=b"{}",
        )
        assert st_post == 403
        _assert_security_headers(h_post)
        assert "access-control-allow-origin" not in h_post
        assert "error" in json.loads(b_post.decode("utf-8"))

        # Untrusted GET omits Access-Control-Allow-Origin
        st_get, h_get, _ = _raw_request(hardened_server, "GET", "/health", headers={"Origin": bad_origin})
        assert st_get == 200
        _assert_security_headers(h_get)
        assert "access-control-allow-origin" not in h_get

    # Allowlisted exact ports (active port and Studio :3000) succeed and echo Origin
    for ok_origin in (f"http://127.0.0.1:{hardened_server}", "http://127.0.0.1:3000"):
        st_opt, h_opt, _ = _raw_request(hardened_server, "OPTIONS", "/api/mosh", headers={"Origin": ok_origin})
        assert st_opt == 204
        assert h_opt.get("access-control-allow-origin") == ok_origin
        _assert_security_headers(h_opt)


def test_head_endpoints_and_security_headers(hardened_server):
    for path in ("/", "/health", "/api/health"):
        status, hdrs, body = _raw_request(hardened_server, "HEAD", path)
        assert status == 200
        assert body == b""
        _assert_security_headers(hdrs)


def test_path_traversal_directory_and_404_json(hardened_server):
    for bad_path in ("/../package.json", "/%2e%2e/package.json", "/assets/", "/assets"):
        status, hdrs, body = _raw_request(hardened_server, "GET", bad_path)
        assert status == 403, f"Expected 403 for {bad_path}, got {status}"
        _assert_security_headers(hdrs)
        assert "error" in json.loads(body.decode("utf-8"))

    status, hdrs, body = _raw_request(hardened_server, "GET", "/nonexistent-404")
    assert status == 404
    _assert_security_headers(hdrs)
    assert "error" in json.loads(body.decode("utf-8"))


def test_post_payload_cap_413_and_invalid_content_length(hardened_server):
    oversized = b"{" + b" " * (MAX_BODY_BYTES + 128) + b"}"
    status, hdrs, body = _raw_request(
        hardened_server,
        "POST",
        "/api/mosh",
        headers={"Content-Type": "application/json"},
        body=oversized,
    )
    assert status == 413
    _assert_security_headers(hdrs)
    assert "error" in json.loads(body.decode("utf-8"))


def test_malformed_query_zero_div_bad_base64_and_bounds_return_400(hardened_server):
    # Bad query & too small width
    for q in ("/api/bitplane-mosaic?width=abc", "/api/bitplane-mosaic?width=5&height=5", "/api/bitplane-mosaic?width=9999&height=9999"):
        status, hdrs, body = _raw_request(hardened_server, "GET", q)
        assert status == 400, f"Expected 400 for {q}, got {status}"
        _assert_security_headers(hdrs)
        assert "error" in json.loads(body.decode("utf-8"))

    # POST invalid dimensions / zero block_size / bad base64 / invalid JSON
    cases = [
        ("/api/mosh", b"{bad-json"),
        ("/api/mosh", json.dumps({"width": 5, "height": 5}).encode()),
        ("/api/mosh", json.dumps({"width": 4096, "height": 4096}).encode()),
        ("/api/motion-estimate", json.dumps({"block_size": 0}).encode()),
        ("/api/corrupt", json.dumps({"data_base64": "!!!not-base64!!!"}).encode()),
        ("/api/sequence", json.dumps({"frames_count": 100}).encode()),
    ]
    for path, payload in cases:
        status, hdrs, body = _raw_request(
            hardened_server,
            "POST",
            path,
            headers={"Content-Type": "application/json"},
            body=payload,
        )
        assert status == 400, f"Expected 400 for {path} {payload!r}, got {status}"
        _assert_security_headers(hdrs)
        assert "error" in json.loads(body.decode("utf-8"))


def test_svg_xss_channel_rejected_and_html_title_escaped(hardened_server):
    payload_ch = urllib.parse.quote("</text><script>alert(1)</script><text>", safe="")
    status, hdrs, body = _raw_request(
        hardened_server,
        "GET",
        f"/api/bitplane-mosaic?width=32&height=32&channel={payload_ch}",
    )
    assert status == 400
    _assert_security_headers(hdrs)
    assert "<script>" not in body.decode("utf-8").lower()

    frame = ImageFrame.create(32, 32)
    with pytest.raises(ValueError):
        BitplaneGlitchEngine.render_bitplane_mosaic_svg(frame, channel="</text><script>alert(1)</script><text>")

    html_out = export_frame_sequence_html([frame], title='"><script>alert(1)</script>')
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_out


def test_bmp_and_ppm_oom_bomb_and_motion_bounds():
    # Craft 54-byte BMP claiming 100000 x 100000
    bmp_bomb = struct.pack("<2sIHHI", b"BM", 54, 0, 0, 54) + struct.pack(
        "<IiiHHIIiiII", 40, 100000, 100000, 1, 24, 0, 0, 2835, 2835, 0, 0
    )
    with pytest.raises(ValueError):
        ImageFrame.from_bmp(bmp_bomb)

    # Craft PPM claiming 50000 x 50000
    ppm_bomb = b"P6\n50000 50000\n255\n\x00\x00\x00"
    with pytest.raises(ValueError):
        ImageFrame.from_ppm(ppm_bomb)

    with pytest.raises(ValueError):
        MotionVectorEngine(block_size=0)
    with pytest.raises(ValueError):
        MotionVectorEngine(block_size=256)
