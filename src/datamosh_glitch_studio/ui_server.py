"""
Datamosh Glitch Studio Loopback HTTP UI & REST API Server (v2.6.0).
Zero third-party runtime dependencies.
Strict loopback Host allowlist, exact-port CORS, security headers, 1 MiB body cap,
and deterministic input validation across all codec and glitch endpoints.
"""

from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from datamosh_glitch_studio.bitplane_glitch import (
    ALLOWED_CHANNELS,
    BitplaneGlitchEngine,
)
from datamosh_glitch_studio.frame_io import (
    MAX_HEIGHT,
    MAX_PIXELS,
    MAX_WIDTH,
    ImageFrame,
)
from datamosh_glitch_studio.glitch_core import DatamoshEngine, corrupt_byte_stream
from datamosh_glitch_studio.motion_vector_engine import (
    MotionVectorEngine,
    render_motion_vectors_ascii,
    render_motion_vectors_svg,
)
from datamosh_glitch_studio.presets import PRESETS, get_preset, list_presets

SERVER_VERSION = "2.6.0"
SERVER_START_TIME = time.time()

MAX_BODY_BYTES = 1048576  # 1 MiB
MIN_DIM = 16
MAX_DIM = 2048
MIN_BLOCK_SIZE = 4
MAX_BLOCK_SIZE = 128
MIN_FRAMES = 1
MAX_FRAMES = 60

ALLOWED_FORMULAS = frozenset({"xor", "and", "or", "xor_and"})

CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "media-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'self' http://127.0.0.1:* http://localhost:*"
)


def _is_allowed_host(host_header: Optional[str], server_port: int = 8081) -> bool:
    """Validate Host header against strict loopback allowlist (DNS-rebinding defense)."""
    if not host_header:
        return False
    raw = host_header.strip()
    if not raw or any(ch.isspace() for ch in raw) or "/" in raw or "@" in raw:
        return False

    hostname = ""
    port_str: Optional[str] = None

    if raw.startswith("["):
        end = raw.find("]")
        if end == -1:
            return False
        hostname = raw[1:end].lower()
        rest = raw[end + 1:]
        if rest:
            if not rest.startswith(":"):
                return False
            port_str = rest[1:]
    elif ":" in raw:
        parts = raw.rsplit(":", 1)
        hostname = parts[0].lower()
        port_str = parts[1]
    else:
        hostname = raw.lower()

    if hostname not in ("127.0.0.1", "localhost", "::1"):
        return False

    if port_str is not None:
        if not port_str.isdigit():
            return False
        port = int(port_str)
        if port < 1 or port > 65535:
            return False
        if server_port and port != int(server_port):
            return False

    return True


def _is_local_origin(origin: Optional[str], server_port: int = 8081) -> bool:
    """True for omitted Origin (same-origin/CLI) or exact-port loopback origin (:server_port or :3000)."""
    if not origin:
        return True
    try:
        u = urllib.parse.urlparse(origin)
    except Exception:
        return False
    if u.scheme != "http":
        return False
    if (u.hostname or "").lower() not in ("localhost", "127.0.0.1", "::1"):
        return False
    if u.username or u.password or u.path not in ("", "/") or u.query or u.fragment:
        return False
    try:
        port = u.port
    except ValueError:
        return False
    allowed_ports = {int(server_port), 3000}
    return port in allowed_ports


def _parse_int(value: Any, name: str, min_val: int, max_val: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        iv = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer")
    if iv < min_val or iv > max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {iv}")
    return iv


def _parse_float(value: Any, name: str, min_val: float, max_val: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    try:
        fv = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number")
    if fv != fv or fv < min_val or fv > max_val:  # NaN or out of range
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {fv}")
    return fv


def _parse_dims(width_raw: Any, height_raw: Any) -> Tuple[int, int]:
    w = _parse_int(width_raw, "width", MIN_DIM, MAX_DIM)
    h = _parse_int(height_raw, "height", MIN_DIM, MAX_DIM)
    if w * h > MAX_PIXELS:
        raise ValueError(f"Total pixel count exceeds {MAX_PIXELS}")
    return w, h


def _decode_b64(data_b64: Any, name: str = "data_base64") -> bytes:
    if not isinstance(data_b64, str) or not data_b64.strip():
        raise ValueError(f"{name} must be a non-empty base64 string")
    try:
        return base64.b64decode(data_b64.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid base64 in {name}: {exc}") from exc


def _decode_frame_from_b64(img_b64: str) -> ImageFrame:
    raw_img = _decode_b64(img_b64, "image_base64")
    if raw_img.startswith(b"BM"):
        return ImageFrame.from_bmp(raw_img)
    if raw_img.startswith(b"P6"):
        return ImageFrame.from_ppm(raw_img)
    raise ValueError("Unsupported image format: expected 24/32-bit BMP or P6 PPM")


def _make_color_bars(
    w: int,
    h: int,
    colors: Optional[List[Tuple[int, int, int]]] = None,
) -> ImageFrame:
    palette = colors or [
        (255, 255, 255),
        (255, 255, 0),
        (0, 255, 255),
        (0, 255, 0),
        (255, 0, 255),
        (255, 0, 0),
        (0, 0, 255),
    ]
    frame = ImageFrame.create(w, h)
    bw = max(1, w // len(palette))
    last = len(palette) - 1
    for y in range(h):
        for x in range(w):
            frame.set_pixel(x, y, palette[min(last, x // bw)])
    return frame


def _parse_bit_list(val: Any, name: str) -> List[int]:
    if not isinstance(val, list):
        raise ValueError(f"{name} must be a list of bit indices (0..7)")
    bits: List[int] = []
    for item in val:
        bits.append(_parse_int(item, f"{name} element", 0, 7))
    return bits


class DatamoshHTTPHandler(BaseHTTPRequestHandler):
    """Hardened HTTP Request Handler for Datamosh Glitch Studio Web UI and REST API."""

    def _server_port(self) -> int:
        try:
            return int(self.server.server_address[1])
        except Exception:
            return 8081

    def _public_dir(self) -> str:
        return os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "public"))

    def _send_security_and_cors_headers(self) -> None:
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Security-Policy", CSP_HEADER)
        self.send_header("Vary", "Origin")

        origin = self.headers.get("Origin", "")
        if origin and _is_local_origin(origin, server_port=self._server_port()):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data: Any, status: int = 200, head_only: bool = False) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_security_and_cors_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_bytes(self, content: bytes, content_type: str, status: int = 200, head_only: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self._send_security_and_cors_headers()
        self.end_headers()
        if not head_only:
            self.wfile.write(content)

    def _check_host(self, head_only: bool = False) -> bool:
        host = self.headers.get("Host")
        if not _is_allowed_host(host, server_port=self._server_port()):
            self._send_json(
                {"error": "Forbidden: invalid Host header (loopback only)"},
                status=403,
                head_only=head_only,
            )
            return False
        return True

    def _check_strict_origin(self, head_only: bool = False) -> bool:
        origin = self.headers.get("Origin")
        if origin and not _is_local_origin(origin, server_port=self._server_port()):
            self._send_json(
                {"error": "Forbidden: cross-origin or non-allowlisted port request blocked"},
                status=403,
                head_only=head_only,
            )
            return False
        return True

    def _resolve_static(self, raw_path: str) -> Tuple[int, Optional[str], Optional[str]]:
        """Resolve static file safely inside public/. Returns (status, file_path, error_msg)."""
        # Inspect raw and percent-decoded path for traversal indicators
        decoded = urllib.parse.unquote(raw_path)
        for candidate in (raw_path, decoded):
            if "\x00" in candidate or "\\" in candidate:
                return 403, None, "Forbidden: invalid path"
            parts = [p for p in candidate.split("/") if p]
            if any(p == ".." for p in parts):
                return 403, None, "Forbidden: path traversal blocked"

        public_real = self._public_dir()
        rel = decoded.lstrip("/")
        if not rel or rel == "index.html":
            target = os.path.realpath(os.path.join(public_real, "index.html"))
        else:
            target = os.path.realpath(os.path.join(public_real, rel))

        try:
            common = os.path.commonpath([public_real, target])
        except ValueError:
            return 403, None, "Forbidden: path outside public root"

        if common != public_real:
            return 403, None, "Forbidden: path outside public root"

        if os.path.isdir(target):
            return 403, None, "Forbidden: directory listing disabled"

        if not os.path.isfile(target):
            return 404, None, f"Not found: {raw_path}"

        return 200, target, None

    def _handle_get_or_head(self, head_only: bool = False) -> None:
        if not self._check_host(head_only=head_only):
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            if path in ("/api/health", "/health"):
                self._send_json(
                    {
                        "status": "ok",
                        "service": "datamosh-glitch-studio",
                        "version": SERVER_VERSION,
                        "uptime_seconds": round(time.time() - SERVER_START_TIME, 2),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    head_only=head_only,
                )
                return

            if path == "/api/presets":
                self._send_json({"presets": list_presets(), "version": SERVER_VERSION}, head_only=head_only)
                return

            if path == "/api/diagnostics":
                self._send_json(
                    {
                        "service": "datamosh-glitch-studio",
                        "version": SERVER_VERSION,
                        "platform": sys.platform,
                        "python": sys.version,
                        "presets_count": len(PRESETS),
                        "status": "HEALTHY",
                    },
                    head_only=head_only,
                )
                return

            if path == "/api/bitplane-mosaic":
                qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
                channel = qs.get("channel", ["luminance"])[0]
                if channel.strip().lower() not in ALLOWED_CHANNELS:
                    raise ValueError(f"Invalid channel; must be one of {sorted(ALLOWED_CHANNELS)}")
                w, h = _parse_dims(qs.get("width", ["320"])[0], qs.get("height", ["240"])[0])
                frame = _make_color_bars(w, h)
                svg_code = BitplaneGlitchEngine.render_bitplane_mosaic_svg(frame, channel=channel)
                self._send_json(
                    {
                        "status": "success",
                        "channel": channel.strip().lower(),
                        "width": w,
                        "height": h,
                        "svg_mosaic": svg_code,
                    },
                    head_only=head_only,
                )
                return

            if path.startswith("/api/"):
                self._send_json({"error": f"Endpoint not found: {path}"}, status=404, head_only=head_only)
                return

            status, target_path, err = self._resolve_static(path)
            if status != 200 or not target_path:
                self._send_json({"error": err or "Not found"}, status=status, head_only=head_only)
                return

            ctype, _ = mimetypes.guess_type(target_path)
            if not ctype:
                ctype = "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "application/xml"):
                ctype += "; charset=utf-8"

            with open(target_path, "rb") as f:
                content = f.read()
            self._send_bytes(content, ctype, status=200, head_only=head_only)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400, head_only=head_only)
        except Exception:
            self._send_json({"error": "Internal processing error"}, status=500, head_only=head_only)

    def do_OPTIONS(self) -> None:
        if not self._check_host():
            return
        if not self._check_strict_origin():
            return
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._send_security_and_cors_headers()
        self.end_headers()

    def do_HEAD(self) -> None:
        self._handle_get_or_head(head_only=True)

    def do_GET(self) -> None:
        self._handle_get_or_head(head_only=False)

    def do_POST(self) -> None:
        if not self._check_host():
            return
        if not self._check_strict_origin():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        raw_len = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_len)
        except (TypeError, ValueError):
            self._send_json({"error": "Invalid Content-Length header"}, status=400)
            return

        if length < 0:
            self._send_json({"error": "Negative Content-Length header"}, status=400)
            return

        if length > MAX_BODY_BYTES:
            self._send_json(
                {"error": f"Payload Too Large (max {MAX_BODY_BYTES} bytes)"},
                status=413,
            )
            return

        raw_body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self._send_json({"error": "Invalid JSON body"}, status=400)
            return

        if not isinstance(body, dict):
            self._send_json({"error": "JSON body must be an object"}, status=400)
            return

        try:
            engine = DatamoshEngine()

            if path == "/api/mosh":
                preset_name = str(body.get("preset", "h264_iframe_drop"))
                preset = get_preset(preset_name)
                seed_raw = body.get("seed")
                seed = None if seed_raw is None else _parse_int(seed_raw, "seed", -2_147_483_648, 2_147_483_647)

                img_b64 = body.get("image_base64")
                if img_b64:
                    frame = _decode_frame_from_b64(img_b64)
                else:
                    w, h = _parse_dims(body.get("width", 320), body.get("height", 240))
                    frame = _make_color_bars(w, h)

                glitched = engine.process_frame(frame, preset=preset, seed=seed)
                bmp_bytes = glitched.to_bmp()

                self._send_json(
                    {
                        "status": "success",
                        "preset": preset.name,
                        "width": glitched.width,
                        "height": glitched.height,
                        "image_base64": base64.b64encode(bmp_bytes).decode("ascii"),
                    }
                )
                return

            if path == "/api/sequence":
                preset_name = str(body.get("preset", "h264_iframe_drop"))
                preset = get_preset(preset_name)
                w, h = _parse_dims(body.get("width", 320), body.get("height", 240))
                count = _parse_int(body.get("frames_count", 8), "frames_count", MIN_FRAMES, MAX_FRAMES)
                base_seed = _parse_int(body.get("seed", 42), "seed", -2_147_483_648, 2_147_483_647)

                base_frames = []
                colors = [
                    (255, 255, 255),
                    (255, 255, 0),
                    (0, 255, 255),
                    (0, 255, 0),
                    (255, 0, 255),
                    (255, 0, 0),
                    (0, 0, 255),
                ]
                bw = max(1, w // len(colors))
                for i in range(count):
                    f = ImageFrame.create(w, h)
                    shift = (i * 24) % w
                    for y in range(h):
                        for x in range(w):
                            col_idx = ((x + shift) // bw) % len(colors)
                            f.set_pixel(x, y, colors[col_idx])
                    base_frames.append(f)

                glitched_seq = engine.process_video_sequence(base_frames, preset=preset, seed=base_seed)
                b64_list = [base64.b64encode(gf.to_bmp()).decode("ascii") for gf in glitched_seq]

                self._send_json(
                    {
                        "status": "success",
                        "preset": preset.name,
                        "frames_count": len(b64_list),
                        "frames": b64_list,
                    }
                )
                return

            if path == "/api/corrupt":
                data_b64 = body.get("data_base64", "")
                raw = _decode_b64(data_b64, "data_base64")
                rate = _parse_float(body.get("rate", 0.002), "rate", 0.0, 1.0)
                hdr_skip = _parse_int(body.get("header_skip", 64), "header_skip", 0, MAX_BODY_BYTES)
                corrupted = corrupt_byte_stream(raw, rate=rate, header_skip=hdr_skip)

                self._send_json(
                    {
                        "status": "success",
                        "original_length": len(raw),
                        "corrupted_length": len(corrupted),
                        "corrupted_base64": base64.b64encode(corrupted).decode("ascii"),
                    }
                )
                return

            if path == "/api/motion-estimate":
                w, h = _parse_dims(body.get("width", 160), body.get("height", 120))
                bs = _parse_int(body.get("block_size", 16), "block_size", MIN_BLOCK_SIZE, MAX_BLOCK_SIZE)
                shift_dx = _parse_int(body.get("shift_dx", 4), "shift_dx", -64, 64)
                shift_dy = _parse_int(body.get("shift_dy", 2), "shift_dy", -64, 64)

                ref = _make_color_bars(w, h)
                tgt = ImageFrame.create(w, h)
                for y in range(h):
                    for x in range(w):
                        src_x = (x - shift_dx) % w
                        src_y = (y - shift_dy) % h
                        tgt.set_pixel(x, y, ref.get_pixel(src_x, src_y))

                mv_engine = MotionVectorEngine(block_size=bs)
                mv_field = mv_engine.estimate_motion(ref, tgt)

                self._send_json(
                    {
                        "status": "success",
                        "width": w,
                        "height": h,
                        "block_size": bs,
                        "total_blocks": len(mv_field.vectors),
                        "average_magnitude": round(mv_field.average_magnitude, 3),
                        "ascii_flow_grid": render_motion_vectors_ascii(mv_field),
                        "svg_vector_map": render_motion_vectors_svg(mv_field),
                    }
                )
                return

            if path == "/api/liquid-melt":
                w, h = _parse_dims(body.get("width", 160), body.get("height", 120))
                steps = _parse_int(body.get("steps", 6), "steps", MIN_FRAMES, MAX_FRAMES)
                acc = _parse_float(body.get("acceleration", 1.2), "acceleration", 0.1, 4.0)

                ref = _make_color_bars(w, h, [(255, 0, 128), (0, 255, 255), (255, 255, 0), (0, 255, 0)])
                mv_engine = MotionVectorEngine(block_size=16)
                frames = mv_engine.datamosh_liquid_melt(ref, steps=steps, acceleration=acc)
                b64_list = [base64.b64encode(f.to_bmp()).decode("ascii") for f in frames]

                self._send_json(
                    {
                        "status": "success",
                        "steps": steps,
                        "frames_count": len(b64_list),
                        "frames": b64_list,
                    }
                )
                return

            if path == "/api/bitplane-slice":
                keep_bits = _parse_bit_list(body.get("keep_bits", [7, 6, 5]), "keep_bits")
                invert_bits = _parse_bit_list(body.get("invert_bits", []), "invert_bits")
                channel = str(body.get("channel", "all")).strip().lower()
                if channel not in ALLOWED_CHANNELS:
                    raise ValueError(f"Invalid channel; must be one of {sorted(ALLOWED_CHANNELS)}")

                img_b64 = body.get("image_base64")
                if img_b64:
                    frame = _decode_frame_from_b64(img_b64)
                else:
                    w, h = _parse_dims(body.get("width", 320), body.get("height", 240))
                    frame = _make_color_bars(w, h)

                sliced = BitplaneGlitchEngine.slice_bitplanes(frame, keep_bits=keep_bits, channel=channel)
                if invert_bits:
                    sliced = BitplaneGlitchEngine.invert_bitplanes(sliced, invert_bits=invert_bits, channel=channel)

                bmp_bytes = sliced.to_bmp()
                self._send_json(
                    {
                        "status": "success",
                        "width": sliced.width,
                        "height": sliced.height,
                        "keep_bits": keep_bits,
                        "invert_bits": invert_bits,
                        "channel": channel,
                        "image_base64": base64.b64encode(bmp_bytes).decode("ascii"),
                    }
                )
                return

            if path == "/api/sierpinski-xor":
                scale = _parse_float(body.get("scale", 1.0), "scale", 0.05, 16.0)
                blend = _parse_float(body.get("blend", 0.5), "blend", 0.0, 1.0)
                formula = str(body.get("formula", "xor")).strip().lower()
                if formula not in ALLOWED_FORMULAS:
                    raise ValueError(f"Invalid formula; must be one of {sorted(ALLOWED_FORMULAS)}")

                img_b64 = body.get("image_base64")
                if img_b64:
                    frame = _decode_frame_from_b64(img_b64)
                else:
                    w, h = _parse_dims(body.get("width", 320), body.get("height", 240))
                    frame = _make_color_bars(w, h)

                glitched = BitplaneGlitchEngine.xor_sierpinski_glitch(
                    frame, scale=scale, blend=blend, formula=formula
                )
                bmp_bytes = glitched.to_bmp()
                self._send_json(
                    {
                        "status": "success",
                        "formula": formula,
                        "scale": scale,
                        "blend": blend,
                        "width": glitched.width,
                        "height": glitched.height,
                        "image_base64": base64.b64encode(bmp_bytes).decode("ascii"),
                    }
                )
                return

            self._send_json({"error": f"Endpoint not found: {path}"}, status=404)
        except (ValueError, KeyError, TypeError, ZeroDivisionError, binascii.Error) as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception:
            self._send_json({"error": "Internal processing error"}, status=500)

    def log_message(self, format: str, *args: Any) -> None:
        pass


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def run_ui_server(host: str = "127.0.0.1", port: int = 8081) -> ThreadingHTTPServer:
    """Launch hardened loopback UI & REST API HTTP Server."""
    server = ReusableThreadingHTTPServer((host, port), DatamoshHTTPHandler)
    return server
