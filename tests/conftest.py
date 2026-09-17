import os
import sys
from pathlib import Path
import pytest

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datamosh_glitch_studio.frame_io import ImageFrame


@pytest.fixture
def sample_rgb_frame() -> ImageFrame:
    """Fixture returning a 64x64 solid colored frame."""
    return ImageFrame.create(64, 64, (200, 100, 50))


@pytest.fixture
def gradient_frame() -> ImageFrame:
    """Fixture returning a 32x32 color gradient frame."""
    frame = ImageFrame.create(32, 32)
    for y in range(32):
        for x in range(32):
            frame.set_pixel(x, y, (x * 8, y * 8, (x + y) * 4))
    return frame
