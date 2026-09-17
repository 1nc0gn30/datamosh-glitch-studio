"""
Tests for Motion Vector Engine: Macroblock Optical Flow, I-Frame Drop Datamoshing, and Liquid Melt.
Zero external runtime dependencies.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from datamosh_glitch_studio.cli import main
from datamosh_glitch_studio.frame_io import ImageFrame
from datamosh_glitch_studio.mcp_server import MCPServer
from datamosh_glitch_studio.motion_vector_engine import (
    FrameType,
    MacroblockMotionVector,
    MotionVectorEngine,
    MotionVectorField,
    render_motion_vectors_ascii,
    render_motion_vectors_svg,
)


def _create_sample_frame(width: int = 64, height: int = 64) -> ImageFrame:
    frame = ImageFrame.create(width, height)
    for y in range(height):
        for x in range(width):
            r = (x * 4) % 256
            g = (y * 4) % 256
            b = ((x + y) * 2) % 256
            frame.set_pixel(x, y, (r, g, b))
    return frame


def test_motion_vector_estimation_zero_motion() -> None:
    frame = _create_sample_frame(32, 32)
    engine = MotionVectorEngine(block_size=8, search_range=4)
    mv_field = engine.estimate_motion(frame, frame)

    assert mv_field.width == 32
    assert mv_field.height == 32
    assert mv_field.block_size == 8
    assert len(mv_field.vectors) == 16  # (32/8) * (32/8) = 16 blocks
    assert mv_field.average_magnitude == 0.0
    for v in mv_field.vectors:
        assert v.dx == 0
        assert v.dy == 0
        assert v.sad == 0.0


def test_motion_vector_estimation_uniform_shift() -> None:
    w, h = 32, 32
    ref = _create_sample_frame(w, h)
    shift_dx, shift_dy = 2, 0

    tgt = ImageFrame.create(w, h)
    for y in range(h):
        for x in range(w):
            src_x = (x - shift_dx) % w
            src_y = (y - shift_dy) % h
            tgt.set_pixel(x, y, ref.get_pixel(src_x, src_y))

    engine = MotionVectorEngine(block_size=8, search_range=4)
    mv_field = engine.estimate_motion(ref, tgt)

    assert mv_field.average_magnitude > 0.0
    # Center blocks should detect the horizontal shift of 2
    matched = [v for v in mv_field.vectors if abs(v.dx) == 2 and v.dy == 0]
    assert len(matched) > 0


def test_apply_motion_vectors_warping() -> None:
    frame = _create_sample_frame(32, 32)
    engine = MotionVectorEngine(block_size=8)
    vectors = [
        MacroblockMotionVector(mb_x=x, mb_y=y, dx=4, dy=0, sad=0.0)
        for y in range(0, 32, 8)
        for x in range(0, 32, 8)
    ]
    mv_field = MotionVectorField(width=32, height=32, block_size=8, vectors=vectors, average_magnitude=4.0)

    warped = engine.apply_motion_vectors(frame, mv_field)
    assert warped.width == 32
    assert warped.height == 32
    # The warped data should differ from the original frame
    assert warped.data != frame.data


def test_datamosh_iframe_kill() -> None:
    scene_a = _create_sample_frame(32, 32)
    scene_b_frames = [_create_sample_frame(32, 32) for _ in range(4)]

    engine = MotionVectorEngine(block_size=8)
    mosh_frames = engine.datamosh_iframe_kill(scene_a, scene_b_frames, vector_multiplier=1.2)

    assert len(mosh_frames) == 4
    for mf in mosh_frames:
        assert mf.width == 32
        assert mf.height == 32


def test_datamosh_liquid_melt() -> None:
    frame = _create_sample_frame(32, 32)
    engine = MotionVectorEngine(block_size=8)
    melt_sequence = engine.datamosh_liquid_melt(frame, steps=4, acceleration=1.1)

    assert len(melt_sequence) == 5  # Initial frame + 4 steps
    for mf in melt_sequence:
        assert mf.width == 32
        assert mf.height == 32


def test_render_motion_vectors_svg_and_ascii() -> None:
    vectors = [
        MacroblockMotionVector(mb_x=0, mb_y=0, dx=3, dy=0, sad=10.0),
        MacroblockMotionVector(mb_x=8, mb_y=0, dx=0, dy=2, sad=5.0),
        MacroblockMotionVector(mb_x=0, mb_y=8, dx=0, dy=0, sad=0.0),
    ]
    mv_field = MotionVectorField(width=16, height=16, block_size=8, vectors=vectors, average_magnitude=1.5)

    svg_out = render_motion_vectors_svg(mv_field)
    assert svg_out.startswith("<svg")
    assert "</svg>" in svg_out
    assert "<line" in svg_out

    ascii_out = render_motion_vectors_ascii(mv_field)
    assert "→" in ascii_out
    assert "·" in ascii_out


def test_mcp_motion_vector_tools() -> None:
    server = MCPServer()

    # datamosh_motion_estimate
    res_est = server.handle_tool_call(
        "datamosh_motion_estimate",
        {"width": 64, "height": 48, "block_size": 16, "shift_dx": 2, "shift_dy": 1}
    )
    data_est = json.loads(res_est["content"][0]["text"])
    assert data_est["width"] == 64
    assert data_est["total_blocks"] > 0
    assert "svg_vector_map" in data_est
    assert "ascii_flow_grid" in data_est

    # datamosh_liquid_melt
    res_melt = server.handle_tool_call(
        "datamosh_liquid_melt",
        {"width": 64, "height": 48, "steps": 3}
    )
    data_melt = json.loads(res_melt["content"][0]["text"])
    assert data_melt["status"] == "success"
    assert data_melt["frames_count"] == 4


def test_cli_motion_and_melt_commands(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    # CLI motion --json
    code_m = main(["motion", "--width", "64", "--height", "48", "--json"])
    assert code_m == 0
    out_m = capsys.readouterr().out
    data_m = json.loads(out_m)
    assert data_m["total_blocks"] > 0

    # CLI melt
    out_html = str(tmp_path / "test_melt.html")
    code_melt = main(["melt", "--steps", "3", "-o", out_html])
    assert code_melt == 0
    out_melt = capsys.readouterr().out
    assert "Liquid melt" in out_melt
