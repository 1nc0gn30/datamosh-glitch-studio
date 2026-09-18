"""Tests for Bitplane Slicer, Inverter, Permuter, and Spatial XOR Glitch Engine."""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any, Dict

import pytest

from datamosh_glitch_studio.bitplane_glitch import (
    BitplaneExtractor,
    BitplaneGlitchEngine,
)
from datamosh_glitch_studio.cli import main
from datamosh_glitch_studio.frame_io import ImageFrame
from datamosh_glitch_studio.mcp_server import MCPServer
from datamosh_glitch_studio.ui_server import run_ui_server


@pytest.fixture
def gradient_frame() -> ImageFrame:
    """Provide a 64x64 test frame with predictable RGB gradients."""
    frame = ImageFrame.create(64, 64)
    for y in range(64):
        for x in range(64):
            frame.set_pixel(x, y, (x * 4, y * 4, (x + y) * 2))
    return frame


class TestBitplaneExtractor:
    """Test decomposing frames into binary bitplanes."""

    @pytest.mark.parametrize("bit", range(8))
    def test_extract_bitplane_binary_values(self, gradient_frame: ImageFrame, bit: int) -> None:
        """Verify extracted bitplanes contain only 0 and 255 values."""
        bp = BitplaneExtractor.extract_bitplane(gradient_frame, bit=bit, channel="luminance")
        assert bp.width == gradient_frame.width
        assert bp.height == gradient_frame.height

        for y in range(0, bp.height, 8):
            for x in range(0, bp.width, 8):
                r, g, b = bp.get_pixel(x, y)
                assert r in (0, 255)
                assert g in (0, 255)
                assert b in (0, 255)

    def test_extract_all_bitplanes(self, gradient_frame: ImageFrame) -> None:
        """Verify extracting all 8 bitplanes returns exactly 8 frames."""
        planes = BitplaneExtractor.extract_all_bitplanes(gradient_frame)
        assert len(planes) == 8

    def test_extract_invalid_bit(self, gradient_frame: ImageFrame) -> None:
        """Verify invalid bit index raises ValueError."""
        with pytest.raises(ValueError, match="Bit index must be 0..7"):
            BitplaneExtractor.extract_bitplane(gradient_frame, bit=8)

        with pytest.raises(ValueError, match="Bit index must be 0..7"):
            BitplaneExtractor.extract_bitplane(gradient_frame, bit=-1)


class TestBitplaneGlitchEngine:
    """Test bitplane manipulation and spatial boolean syntheses."""

    def test_slice_bitplanes_msb(self, gradient_frame: ImageFrame) -> None:
        """Verify keeping only MSB (Bit 7) restricts values to 0 or 128."""
        sliced = BitplaneGlitchEngine.slice_bitplanes(gradient_frame, keep_bits=[7], channel="all")
        for y in range(0, sliced.height, 8):
            for x in range(0, sliced.width, 8):
                r, g, b = sliced.get_pixel(x, y)
                assert r in (0, 128)
                assert g in (0, 128)
                assert b in (0, 128)

    def test_invert_bitplanes(self) -> None:
        """Verify inverting bit 7 flips 0 to 128 and 128 to 0."""
        frame = ImageFrame.create(10, 10, color=(0, 0, 0))
        inv = BitplaneGlitchEngine.invert_bitplanes(frame, invert_bits=[7], channel="all")
        assert inv.get_pixel(0, 0) == (128, 128, 128)

    def test_channel_bit_swap(self) -> None:
        """Verify swapping bit 7 of Red with bit 7 of Blue."""
        frame = ImageFrame.create(10, 10, color=(128, 0, 0))
        swapped = BitplaneGlitchEngine.channel_bit_swap(frame, "r", 7, "b", 7)
        assert swapped.get_pixel(0, 0) == (0, 0, 128)

    def test_channel_bit_swap_invalid_channel(self, gradient_frame: ImageFrame) -> None:
        """Verify invalid channel raises ValueError."""
        with pytest.raises(ValueError, match="Channels must be 'r', 'g', or 'b'"):
            BitplaneGlitchEngine.channel_bit_swap(gradient_frame, "x", 0, "r", 0)

    @pytest.mark.parametrize("formula", ["xor", "and", "or", "xor_and"])
    def test_xor_sierpinski_glitch(self, gradient_frame: ImageFrame, formula: str) -> None:
        """Verify spatial boolean texture glitch modifies frame."""
        glitched = BitplaneGlitchEngine.xor_sierpinski_glitch(
            gradient_frame, scale=1.5, blend=0.8, formula=formula
        )
        assert glitched.width == gradient_frame.width
        assert glitched.height == gradient_frame.height
        assert glitched.data != gradient_frame.data

    def test_ordered_dither_glitch(self, gradient_frame: ImageFrame) -> None:
        """Verify ordered dithering quantizes pixels."""
        dithered = BitplaneGlitchEngine.ordered_dither_glitch(gradient_frame, levels=4)
        assert dithered.width == gradient_frame.width
        assert dithered.height == gradient_frame.height

    def test_render_bitplane_mosaic_svg(self, gradient_frame: ImageFrame) -> None:
        """Verify SVG mosaic generation contains expected tags and labels."""
        svg_str = BitplaneGlitchEngine.render_bitplane_mosaic_svg(gradient_frame, channel="luminance")
        assert "<svg" in svg_str
        assert "Bitplane Glitch Decomposition Matrix" in svg_str
        assert "Bit 7 (MSB)" in svg_str
        assert "Bit 0 (LSB)" in svg_str


class TestBitplaneMCPTools:
    """Test MCP server bitplane tool handlers."""

    def test_mcp_bitplane_slice(self) -> None:
        """Verify datamosh_bitplane_slice MCP tool."""
        server = MCPServer()
        res = server.handle_tool_call("datamosh_bitplane_slice", {
            "keep_bits": [7, 6],
            "channel": "all",
            "width": 64,
            "height": 64,
        })
        assert not res.get("isError", False)
        parsed = json.loads(res["content"][0]["text"])
        assert parsed["status"] == "success"
        assert parsed["keep_bits"] == [7, 6]
        assert "image_base64" in parsed

    def test_mcp_sierpinski_xor(self) -> None:
        """Verify datamosh_sierpinski_xor MCP tool."""
        server = MCPServer()
        res = server.handle_tool_call("datamosh_sierpinski_xor", {
            "formula": "xor",
            "scale": 1.0,
            "blend": 0.5,
            "width": 64,
            "height": 64,
        })
        assert not res.get("isError", False)
        parsed = json.loads(res["content"][0]["text"])
        assert parsed["status"] == "success"
        assert parsed["formula"] == "xor"

    def test_mcp_bitplane_mosaic(self) -> None:
        """Verify datamosh_bitplane_mosaic MCP tool."""
        server = MCPServer()
        res = server.handle_tool_call("datamosh_bitplane_mosaic", {
            "channel": "luminance",
            "width": 64,
            "height": 64,
        })
        assert not res.get("isError", False)
        parsed = json.loads(res["content"][0]["text"])
        assert parsed["status"] == "success"
        assert "<svg" in parsed["svg_mosaic"]


class TestBitplaneCLI:
    """Test bitplane CLI subcommands."""

    def test_cli_bitplane(self, tmp_path: Path) -> None:
        """Verify 'datamosh-studio bitplane' command."""
        out_file = tmp_path / "bitplane_out.bmp"
        mosaic_file = tmp_path / "mosaic.svg"
        code = main([
            "bitplane",
            "--keep-bits", "7,6,5",
            "--mosaic", str(mosaic_file),
            "-o", str(out_file),
            "--width", "64",
            "--height", "64",
        ])
        assert code == 0
        assert out_file.is_file()
        assert out_file.stat().st_size > 0
        assert mosaic_file.is_file()
        assert "<svg" in mosaic_file.read_text(encoding="utf-8")

    def test_cli_xor(self, tmp_path: Path) -> None:
        """Verify 'datamosh-studio xor' command."""
        out_file = tmp_path / "xor_out.bmp"
        code = main([
            "xor",
            "--formula", "xor_and",
            "--scale", "1.2",
            "--blend", "0.6",
            "-o", str(out_file),
            "--width", "64",
            "--height", "64",
        ])
        assert code == 0
        assert out_file.is_file()
        assert out_file.stat().st_size > 0


class TestBitplaneUIEndpoints:
    """Test REST API routes for bitplane and XOR glitch."""

    @pytest.fixture
    def test_server(self) -> Any:
        import socket, threading, time
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        server = run_ui_server("127.0.0.1", port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.05)
        yield f"http://127.0.0.1:{port}"
        server.shutdown()
        server.server_close()
        t.join(timeout=1.0)

    def test_api_bitplane_slice(self, test_server: str) -> None:
        """Verify POST /api/bitplane-slice."""
        payload = json.dumps({
            "keep_bits": [7, 6],
            "channel": "all",
            "width": 64,
            "height": 64,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{test_server}/api/bitplane-slice",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "success"
            assert "image_base64" in data

    def test_api_sierpinski_xor(self, test_server: str) -> None:
        """Verify POST /api/sierpinski-xor."""
        payload = json.dumps({
            "formula": "xor",
            "scale": 1.0,
            "blend": 0.5,
            "width": 64,
            "height": 64,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{test_server}/api/sierpinski-xor",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "success"
            assert "image_base64" in data

    def test_api_bitplane_mosaic(self, test_server: str) -> None:
        """Verify GET /api/bitplane-mosaic."""
        req = urllib.request.Request(f"{test_server}/api/bitplane-mosaic?channel=luminance&width=64&height=64")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "success"
            assert "<svg" in data["svg_mosaic"]
