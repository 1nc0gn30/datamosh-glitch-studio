"""Tests for UI Web Server and REST API."""

import json
import threading
import time
import urllib.request
import pytest
from datamosh_glitch_studio.ui_server import run_ui_server


@pytest.fixture(scope="module")
def live_server():
    server = run_ui_server(host="127.0.0.1", port=8199)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield "http://127.0.0.1:8199"
    server.shutdown()
    server.server_close()


def test_api_health(live_server):
    req = urllib.request.Request(f"{live_server}/api/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert data["service"] == "datamosh-glitch-studio"


def test_api_presets(live_server):
    req = urllib.request.Request(f"{live_server}/api/presets")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert len(data["presets"]) >= 5


def test_api_diagnostics(live_server):
    req = urllib.request.Request(f"{live_server}/api/diagnostics")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "HEALTHY"


def test_api_mosh_post(live_server):
    payload = json.dumps({
        "preset": "cyberpunk_vcr",
        "width": 64,
        "height": 48
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{live_server}/api/mosh",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert "image_base64" in data


def test_ui_index_html(live_server):
    req = urllib.request.Request(f"{live_server}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Datamosh Studio" in content


def test_api_sequence(live_server):
    payload = json.dumps({
        "preset": "cyberpunk_vcr",
        "width": 64,
        "height": 48,
        "frames_count": 3
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/sequence",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert data["frames_count"] == 3
        assert len(data["frames"]) == 3


def test_api_motion_estimate(live_server):
    payload = json.dumps({
        "width": 64,
        "height": 48,
        "block_size": 16,
        "shift_dx": 2,
        "shift_dy": 1
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/motion-estimate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert data["total_blocks"] > 0
        assert "svg_vector_map" in data


def test_api_liquid_melt(live_server):
    payload = json.dumps({
        "width": 64,
        "height": 48,
        "steps": 3
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/liquid-melt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert data["frames_count"] == 4


