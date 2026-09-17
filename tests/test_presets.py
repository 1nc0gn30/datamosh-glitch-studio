"""Tests for preset definitions and metadata queries."""

import pytest
from datamosh_glitch_studio.presets import PRESETS, get_preset, list_presets


def test_presets_catalog():
    assert len(PRESETS) >= 5
    assert "h264_iframe_drop" in PRESETS
    assert "cyberpunk_vcr" in PRESETS
    assert "rgb_split_overdrive" in PRESETS


def test_get_preset():
    p = get_preset("cyberpunk_vcr")
    assert p.id == "cyberpunk_vcr"

    # Default fallback
    p_def = get_preset("non_existent_preset")
    assert p_def.id == "h264_iframe_drop"


def test_list_presets():
    items = list_presets()
    assert len(items) == len(PRESETS)
    for item in items:
        assert "id" in item
        assert "name" in item
        assert "description" in item
