"""Tests for Frame I/O, BMP and PPM encoders/decoders."""

import pytest
from datamosh_glitch_studio.frame_io import ImageFrame, export_frame_sequence_html


def test_image_frame_creation():
    frame = ImageFrame.create(16, 16, (255, 0, 128))
    assert frame.width == 16
    assert frame.height == 16
    assert len(frame.data) == 16 * 16 * 3
    assert frame.get_pixel(0, 0) == (255, 0, 128)
    assert frame.get_pixel(15, 15) == (255, 0, 128)


def test_pixel_get_set():
    frame = ImageFrame.create(8, 8)
    frame.set_pixel(2, 3, (10, 20, 30))
    assert frame.get_pixel(2, 3) == (10, 20, 30)

    # Clamping
    assert frame.get_pixel(100, 100) == frame.get_pixel(7, 7)


def test_frame_copy():
    f1 = ImageFrame.create(10, 10, (1, 2, 3))
    f2 = f1.copy()
    f2.set_pixel(0, 0, (99, 99, 99))
    assert f1.get_pixel(0, 0) == (1, 2, 3)
    assert f2.get_pixel(0, 0) == (99, 99, 99)


def test_bmp_roundtrip():
    orig = ImageFrame.create(23, 17)  # Test non-multiple of 4 width to test row padding
    for y in range(17):
        for x in range(23):
            orig.set_pixel(x, y, ((x * 10) % 256, (y * 15) % 256, ((x + y) * 8) % 256))

    bmp_bytes = orig.to_bmp()
    assert bmp_bytes.startswith(b"BM")

    decoded = ImageFrame.from_bmp(bmp_bytes)
    assert decoded.width == orig.width
    assert decoded.height == orig.height

    for y in range(17):
        for x in range(23):
            assert decoded.get_pixel(x, y) == orig.get_pixel(x, y)


def test_ppm_roundtrip():
    orig = ImageFrame.create(20, 15)
    for y in range(15):
        for x in range(20):
            orig.set_pixel(x, y, (x * 5, y * 10, 100))

    ppm_bytes = orig.to_ppm()
    assert ppm_bytes.startswith(b"P6\n")

    decoded = ImageFrame.from_ppm(ppm_bytes)
    assert decoded.width == 20
    assert decoded.height == 15
    assert decoded.get_pixel(5, 5) == orig.get_pixel(5, 5)


def test_export_frame_sequence_html():
    frames = [ImageFrame.create(16, 16, (i * 20, 0, 0)) for i in range(5)]
    html = export_frame_sequence_html(frames, fps=10, title="Test Sequence")
    assert "<!DOCTYPE html>" in html
    assert "data:image/bmp;base64," in html
    assert "Test Sequence" in html
