"""Tests for DatamoshEngine and glitch synthesis algorithms."""

import random
import pytest
from datamosh_glitch_studio.frame_io import ImageFrame
from datamosh_glitch_studio.glitch_core import DatamoshEngine, corrupt_byte_stream
from datamosh_glitch_studio.presets import PRESETS, get_preset


def test_horizontal_slice_shift(gradient_frame):
    shifted = DatamoshEngine.apply_horizontal_slice_shift(
        gradient_frame,
        slice_height=4,
        shift_max=10,
        rng=random.Random(42)
    )
    assert shifted.width == gradient_frame.width
    assert shifted.height == gradient_frame.height
    assert shifted.data != gradient_frame.data


def test_vertical_block_shift(gradient_frame):
    shifted = DatamoshEngine.apply_vertical_block_shift(
        gradient_frame,
        block_width=8,
        shift_max=6,
        rng=random.Random(42)
    )
    assert shifted.width == gradient_frame.width
    assert shifted.height == gradient_frame.height
    assert shifted.data != gradient_frame.data


def test_rgb_split(gradient_frame):
    split = DatamoshEngine.apply_rgb_split(gradient_frame, shift_x=4, shift_y=2)
    assert split.width == gradient_frame.width
    assert split.height == gradient_frame.height
    assert split.data != gradient_frame.data


def test_scanlines(gradient_frame):
    scanned = DatamoshEngine.apply_scanlines(gradient_frame, intensity=0.5, frequency=2)
    assert scanned.width == gradient_frame.width
    # Even rows should be darkened compared to original
    orig_px = gradient_frame.get_pixel(10, 2)
    scanned_px = scanned.get_pixel(10, 2)
    assert scanned_px[0] <= orig_px[0]


def test_macroblock_corruption(gradient_frame):
    corrupted = DatamoshEngine.apply_macroblock_corruption(
        gradient_frame,
        block_size=8,
        probability=0.8,
        rng=random.Random(42)
    )
    assert corrupted.width == gradient_frame.width
    assert corrupted.data != gradient_frame.data


def test_ghost_blend(gradient_frame):
    f2 = ImageFrame.create(32, 32, (255, 255, 255))
    blended = DatamoshEngine.apply_ghost_blend(gradient_frame, f2, blend_factor=0.5)
    assert blended.width == gradient_frame.width
    # Pixels should be blended between gradient and white
    assert blended.data != gradient_frame.data


def test_noise(gradient_frame):
    noisy = DatamoshEngine.apply_noise(gradient_frame, intensity=0.3, rng=random.Random(42))
    assert noisy.data != gradient_frame.data


def test_process_frame_with_all_presets(gradient_frame):
    engine = DatamoshEngine()
    for preset_id, preset in PRESETS.items():
        res = engine.process_frame(gradient_frame, preset=preset, seed=123)
        assert res.width == gradient_frame.width
        assert res.height == gradient_frame.height
        assert len(res.data) == len(gradient_frame.data)


def test_process_video_sequence(gradient_frame):
    engine = DatamoshEngine()
    frames = [gradient_frame.copy() for _ in range(4)]
    seq = engine.process_video_sequence(frames)
    assert len(seq) == 4
    for f in seq:
        assert f.width == gradient_frame.width


def test_corrupt_byte_stream():
    data = b"HEADER_1234567890_" * 4 + b"BODY_PAYLOAD_BYTES_TO_CORRUPT_" * 20
    corrupted = corrupt_byte_stream(data, rate=0.05, header_skip=16, seed=42)
    assert len(corrupted) == len(data)
    # Header should be preserved
    assert corrupted[:16] == data[:16]
    # Body should have mutations
    assert corrupted[16:] != data[16:]
