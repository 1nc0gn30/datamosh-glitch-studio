"""
Pure Python Frame I/O and Image Codecs for datamosh-glitch-studio.
Supports 24-bit RGB BMP, PPM (P3/P6), raw bytes, and HTML animation bundles.
Zero third-party runtime dependencies.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from datamosh_glitch_studio.compat import atomic_write_bytes, atomic_write_text, normalize_path


@dataclass
class ImageFrame:
    """Represents a single uncompressed 24-bit RGB video/image frame."""
    width: int
    height: int
    data: bytearray  # Raw RGBRGB... bytes (length = width * height * 3)

    @classmethod
    def create(cls, width: int, height: int, color: Tuple[int, int, int] = (0, 0, 0)) -> ImageFrame:
        """Create a blank frame of specified dimensions and color."""
        r, g, b = color
        row = bytes([r, g, b]) * width
        data = bytearray(row * height)
        return cls(width=width, height=height, data=data)

    @classmethod
    def from_bytes(cls, width: int, height: int, rgb_bytes: bytes) -> ImageFrame:
        """Construct from existing RGB byte sequence."""
        expected_len = width * height * 3
        if len(rgb_bytes) < expected_len:
            # Pad if shorter
            padded = bytearray(rgb_bytes) + bytearray(expected_len - len(rgb_bytes))
            return cls(width=width, height=height, data=padded)
        return cls(width=width, height=height, data=bytearray(rgb_bytes[:expected_len]))

    def copy(self) -> ImageFrame:
        """Create an independent deep copy of the frame."""
        return ImageFrame(width=self.width, height=self.height, data=bytearray(self.data))

    def get_pixel(self, x: int, y: int) -> Tuple[int, int, int]:
        """Get (R, G, B) tuple for given coordinates with boundary clamping."""
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        idx = (y * self.width + x) * 3
        return (self.data[idx], self.data[idx + 1], self.data[idx + 2])

    def set_pixel(self, x: int, y: int, color: Tuple[int, int, int]) -> None:
        """Set (R, G, B) value for given coordinates."""
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 3
            self.data[idx] = max(0, min(255, color[0]))
            self.data[idx + 1] = max(0, min(255, color[1]))
            self.data[idx + 2] = max(0, min(255, color[2]))

    def to_bmp(self) -> bytes:
        """Encode frame to standard uncompressed 24-bit Windows BMP format."""
        # Row size must be padded to a multiple of 4 bytes
        row_size = (self.width * 3 + 3) & ~3
        padding_len = row_size - (self.width * 3)
        padding = b"\x00" * padding_len
        image_size = row_size * self.height
        file_size = 54 + image_size

        # BMP Header (14 bytes)
        bmp_header = struct.pack(
            "<2sIHHI",
            b"BM",
            file_size,
            0,
            0,
            54  # Offset to pixel array
        )

        # DIB Header - BITMAPINFOHEADER (40 bytes)
        dib_header = struct.pack(
            "<IiiHHIIiiII",
            40,               # Header size
            self.width,       # Width
            self.height,      # Height (positive = bottom-up)
            1,                # Color planes
            24,               # Bits per pixel (RGB)
            0,                # BI_RGB (uncompressed)
            image_size,       # Image size
            2835,             # Horizontal resolution (72 DPI in pixels/meter)
            2835,             # Vertical resolution
            0,                # Number of colors in palette
            0                 # Important colors
        )

        buf = bytearray()
        buf.extend(bmp_header)
        buf.extend(dib_header)

        # BMP stores rows bottom-to-top in BGR format
        for y in range(self.height - 1, -1, -1):
            row_start = y * self.width * 3
            for x in range(self.width):
                px = row_start + x * 3
                r = self.data[px]
                g = self.data[px + 1]
                b = self.data[px + 2]
                buf.extend(bytes([b, g, r]))
            buf.extend(padding)

        return bytes(buf)

    @classmethod
    def from_bmp(cls, bmp_bytes: bytes) -> ImageFrame:
        """Decode uncompressed 24-bit or 32-bit BMP from bytes."""
        if len(bmp_bytes) < 54 or bmp_bytes[:2] != b"BM":
            raise ValueError("Invalid BMP header signature")

        offset = struct.unpack_from("<I", bmp_bytes, 10)[0]
        header_size = struct.unpack_from("<I", bmp_bytes, 14)[0]
        width, height = struct.unpack_from("<ii", bmp_bytes, 18)
        bpp = struct.unpack_from("<H", bmp_bytes, 28)[0]

        is_top_down = height < 0
        height = abs(height)

        if bpp not in (24, 32):
            raise ValueError(f"Unsupported BMP bit depth: {bpp} (only 24/32-bit supported)")

        bytes_per_pixel = bpp // 8
        row_size = (width * bytes_per_pixel + 3) & ~3
        frame = cls.create(width, height)

        for y_idx in range(height):
            y = y_idx if is_top_down else (height - 1 - y_idx)
            row_offset = offset + y_idx * row_size
            dest_row_offset = y * width * 3

            for x in range(width):
                px_offset = row_offset + x * bytes_per_pixel
                if px_offset + 2 < len(bmp_bytes):
                    b = bmp_bytes[px_offset]
                    g = bmp_bytes[px_offset + 1]
                    r = bmp_bytes[px_offset + 2]
                    dest_px = dest_row_offset + x * 3
                    frame.data[dest_px] = r
                    frame.data[dest_px + 1] = g
                    frame.data[dest_px + 2] = b

        return frame

    def to_ppm(self) -> bytes:
        """Encode to binary Netpbm PPM (P6) format."""
        header = f"P6\n{self.width} {self.height}\n255\n".encode("ascii")
        return header + bytes(self.data)

    @classmethod
    def from_ppm(cls, ppm_bytes: bytes) -> ImageFrame:
        """Decode PPM (P6) from byte stream."""
        bio = io.BytesIO(ppm_bytes)
        magic = bio.readline().strip()
        if magic != b"P6":
            raise ValueError("Only binary P6 PPM format is supported")

        # Skip comments
        line = bio.readline()
        while line.startswith(b"#"):
            line = bio.readline()

        dims = line.split()
        if len(dims) == 2:
            w, h = int(dims[0]), int(dims[1])
            max_val = int(bio.readline().strip())
        else:
            w = int(dims[0])
            h = int(dims[1])
            max_val = int(dims[2])

        pixel_data = bio.read(w * h * 3)
        return cls.from_bytes(w, h, pixel_data)

    def to_data_uri(self, format: str = "bmp") -> str:
        """Encode image to base64 data URI string."""
        import base64
        if format.lower() == "ppm":
            raw = self.to_ppm()
            mime = "image/x-portable-pixmap"
        else:
            raw = self.to_bmp()
            mime = "image/bmp"
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"


def export_frame_sequence_html(
    frames: List[ImageFrame],
    fps: int = 15,
    title: str = "Datamosh Glitch Sequence"
) -> str:
    """Generate a standalone, zero-dependency HTML player for viewing glitched frame sequences."""
    import base64

    bmp_data_uris = []
    for f in frames:
        bmp_b64 = base64.b64encode(f.to_bmp()).decode("ascii")
        bmp_data_uris.append(f"data:image/bmp;base64,{bmp_b64}")

    uris_json = "[" + ",".join(f'"{uri}"' for uri in bmp_data_uris) + "]"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    body {{
      background: #0f172a;
      color: #f8fafc;
      font-family: system-ui, -apple-system, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }}
    .player {{
      background: #1e293b;
      padding: 1.5rem;
      border-radius: 12px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      text-align: center;
    }}
    img {{
      max-width: 100%;
      height: auto;
      image-rendering: pixelated;
      border: 2px solid #334155;
      border-radius: 8px;
    }}
    .controls {{
      margin-top: 1rem;
      display: flex;
      gap: 0.5rem;
      justify-content: center;
    }}
    button {{
      background: #3b82f6;
      color: white;
      border: none;
      padding: 0.5rem 1rem;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
    }}
    button:hover {{ background: #2563eb; }}
  </style>
</head>
<body>
  <div class="player">
    <h2>{title}</h2>
    <img id="viewer" src="{bmp_data_uris[0] if bmp_data_uris else ''}" alt="Frame">
    <div class="controls">
      <button onclick="togglePlay()">Play / Pause</button>
      <button onclick="prevFrame()">Prev</button>
      <button onclick="nextFrame()">Next</button>
      <span id="counter" style="line-height:2rem; margin-left:0.5rem;">Frame 1/{len(frames)}</span>
    </div>
  </div>
  <script>
    const frames = {uris_json};
    let current = 0;
    let playing = true;
    let interval = setInterval(step, {int(1000 / max(1, fps))});

    function step() {{
      if (!playing || frames.length === 0) return;
      current = (current + 1) % frames.length;
      update();
    }}
    function update() {{
      document.getElementById('viewer').src = frames[current];
      document.getElementById('counter').innerText = `Frame ${{current + 1}}/${{frames.length}}`;
    }}
    function togglePlay() {{
      playing = !playing;
    }}
    function prevFrame() {{
      playing = false;
      current = (current - 1 + frames.length) % frames.length;
      update();
    }}
    function nextFrame() {{
      playing = false;
      current = (current + 1) % frames.length;
      update();
    }}
  </script>
</body>
</html>
"""
