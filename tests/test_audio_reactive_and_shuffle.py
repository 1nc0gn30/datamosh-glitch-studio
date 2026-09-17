"""Unit tests for byte shuffle glitch and audio reactive preset modulation."""

import random
from datamosh_glitch_studio import (
    DatamoshEngine,
    ImageFrame,
    get_preset,
    modulate_preset_with_audio,
)


def _make_test_frame(w=64, h=64):
    # Distinct pattern: row gradients
    data = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 3
            data[idx] = x % 256
            data[idx + 1] = y % 256
            data[idx + 2] = (x + y) % 256
    return ImageFrame(width=w, height=h, data=data)


def test_apply_byte_shuffle_glitch():
    frame = _make_test_frame(64, 64)
    rng = random.Random(42)

    shuffled = DatamoshEngine.apply_byte_shuffle_glitch(
        frame, chunk_size=32, shuffle_count=8, rng=rng
    )

    assert shuffled.width == frame.width
    assert shuffled.height == frame.height
    assert len(shuffled.data) == len(frame.data)
    # The bytes should be altered due to swapping
    assert shuffled.data != frame.data
    # Total byte sum should remain identical because it's a permutation/swap
    assert sum(shuffled.data) == sum(frame.data)


def test_modulate_preset_with_audio_idle_vs_beat():
    base = get_preset("h264_iframe_drop")

    # Low energy, no beat
    idle_mod = modulate_preset_with_audio(base, audio_energy=0.1, is_beat=False)
    assert idle_mod.horizontal_shift_max >= base.horizontal_shift_max

    # High energy, on beat
    beat_mod = modulate_preset_with_audio(base, audio_energy=0.9, is_beat=True)
    assert beat_mod.horizontal_shift_max > idle_mod.horizontal_shift_max
    assert beat_mod.color_shift_x > idle_mod.color_shift_x
    assert beat_mod.noise_intensity > idle_mod.noise_intensity


def test_audio_reactive_preset_in_catalog():
    preset = get_preset("audio_reactive_beat")
    assert preset.id == "audio_reactive_beat"
    assert "Audio-Reactive" in preset.name
