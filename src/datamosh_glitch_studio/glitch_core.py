"""
Core Datamosh & Glitch Synthesis Engine.
Zero external runtime dependencies (100% Python Standard Library).
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union

from datamosh_glitch_studio.frame_io import ImageFrame
from datamosh_glitch_studio.presets import GlitchPreset, get_preset


class DatamoshEngine:
    """Parametric digital artifact and datamosh synthesis engine."""

    def __init__(self, default_preset: Optional[GlitchPreset] = None) -> None:
        self.preset = default_preset or get_preset("h264_iframe_drop")

    @staticmethod
    def apply_horizontal_slice_shift(
        frame: ImageFrame,
        slice_height: int = 12,
        shift_max: int = 20,
        rng: Optional[random.Random] = None
    ) -> ImageFrame:
        """Randomly shift horizontal pixel slices horizontally."""
        r = rng or random.Random()
        out = frame.copy()
        w, h = frame.width, frame.height

        for y_start in range(0, h, slice_height):
            y_end = min(h, y_start + slice_height)
            offset = r.randint(-shift_max, shift_max)
            if offset == 0:
                continue

            for y in range(y_start, y_end):
                row_idx = y * w * 3
                orig_row = frame.data[row_idx: row_idx + w * 3]
                
                # Perform circular shift by offset pixels
                eff_offset = offset % w
                split_byte = (w - eff_offset) * 3
                shifted = orig_row[split_byte:] + orig_row[:split_byte]
                out.data[row_idx: row_idx + w * 3] = shifted

        return out

    @staticmethod
    def apply_vertical_block_shift(
        frame: ImageFrame,
        block_width: int = 16,
        shift_max: int = 15,
        rng: Optional[random.Random] = None
    ) -> ImageFrame:
        """Randomly shift vertical column blocks vertically."""
        r = rng or random.Random()
        out = frame.copy()
        w, h = frame.width, frame.height

        for x_start in range(0, w, block_width):
            x_end = min(w, x_start + block_width)
            offset = r.randint(-shift_max, shift_max)
            if offset == 0:
                continue

            for x in range(x_start, x_end):
                col_pixels = []
                for y in range(h):
                    idx = (y * w + x) * 3
                    col_pixels.append((frame.data[idx], frame.data[idx + 1], frame.data[idx + 2]))

                eff_offset = offset % h
                shifted_col = col_pixels[-eff_offset:] + col_pixels[:-eff_offset]

                for y in range(h):
                    idx = (y * w + x) * 3
                    rgb = shifted_col[y]
                    out.data[idx] = rgb[0]
                    out.data[idx + 1] = rgb[1]
                    out.data[idx + 2] = rgb[2]

        return out

    @staticmethod
    def apply_rgb_split(
        frame: ImageFrame,
        shift_x: int = 6,
        shift_y: int = 4
    ) -> ImageFrame:
        """Displace R, G, and B color channels independently to simulate chromatic aberration."""
        out = frame.copy()
        w, h = frame.width, frame.height

        for y in range(h):
            for x in range(w):
                # Sample Red channel with positive offset (+shift_x, +shift_y)
                rx = (x + shift_x) % w
                ry = (y + shift_y) % h
                r_val = frame.data[(ry * w + rx) * 3]

                # Sample Blue channel with negative offset (-shift_x, -shift_y)
                bx = (x - shift_x) % w
                by = (y - shift_y) % h
                b_val = frame.data[(by * w + bx) * 3 + 2]

                # Green channel remains at center (y * w + x)
                g_val = frame.data[(y * w + x) * 3 + 1]

                dest_idx = (y * w + x) * 3
                out.data[dest_idx] = r_val
                out.data[dest_idx + 1] = g_val
                out.data[dest_idx + 2] = b_val

        return out

    @staticmethod
    def apply_scanlines(
        frame: ImageFrame,
        intensity: float = 0.35,
        frequency: int = 4
    ) -> ImageFrame:
        """Simulate cathode-ray tube (CRT) and VCR tracking scanlines."""
        if intensity <= 0.0:
            return frame

        out = frame.copy()
        w, h = frame.width, frame.height
        darken_factor = 1.0 - max(0.0, min(1.0, intensity))

        for y in range(h):
            if y % frequency == 0:
                row_start = y * w * 3
                for i in range(row_start, row_start + w * 3):
                    out.data[i] = int(out.data[i] * darken_factor)

        return out

    @staticmethod
    def apply_macroblock_corruption(
        frame: ImageFrame,
        block_size: int = 16,
        probability: float = 0.25,
        rng: Optional[random.Random] = None
    ) -> ImageFrame:
        """Simulate digital H.264 / MPEG macroblock corruption and frozen pixel clusters."""
        if probability <= 0.0:
            return frame

        r = rng or random.Random()
        out = frame.copy()
        w, h = frame.width, frame.height

        blocks_x = (w + block_size - 1) // block_size
        blocks_y = (h + block_size - 1) // block_size

        for by in range(blocks_y):
            for bx in range(blocks_x):
                if r.random() < probability:
                    # Pick a source block or random solid color
                    src_bx = r.randint(0, blocks_x - 1)
                    src_by = r.randint(0, blocks_y - 1)

                    target_x0 = bx * block_size
                    target_y0 = by * block_size
                    source_x0 = src_bx * block_size
                    source_y0 = src_by * block_size

                    for dy in range(block_size):
                        ty = target_y0 + dy
                        sy = source_y0 + dy
                        if ty >= h or sy >= h:
                            continue
                        for dx in range(block_size):
                            tx = target_x0 + dx
                            sx = source_x0 + dx
                            if tx >= w or sx >= w:
                                continue

                            s_idx = (sy * w + sx) * 3
                            t_idx = (ty * w + tx) * 3
                            out.data[t_idx] = frame.data[s_idx]
                            out.data[t_idx + 1] = frame.data[s_idx + 1]
                            out.data[t_idx + 2] = frame.data[s_idx + 2]

        return out

    @staticmethod
    def apply_ghost_blend(
        current_frame: ImageFrame,
        previous_frame: Optional[ImageFrame],
        blend_factor: float = 0.4
    ) -> ImageFrame:
        """Blend current frame with previous frame to create motion ghosting / P-frame trails."""
        if previous_frame is None or blend_factor <= 0.0:
            return current_frame

        if current_frame.width != previous_frame.width or current_frame.height != previous_frame.height:
            return current_frame

        out = current_frame.copy()
        alpha = max(0.0, min(1.0, blend_factor))
        inv_alpha = 1.0 - alpha

        for i in range(len(current_frame.data)):
            out.data[i] = int(current_frame.data[i] * inv_alpha + previous_frame.data[i] * alpha)

        return out

    @staticmethod
    def apply_noise(
        frame: ImageFrame,
        intensity: float = 0.15,
        rng: Optional[random.Random] = None
    ) -> ImageFrame:
        """Add analog RF / sensor static noise to image frame."""
        if intensity <= 0.0:
            return frame

        r = rng or random.Random()
        out = frame.copy()
        max_delta = int(255 * intensity)

        for i in range(len(out.data)):
            if r.random() < 0.4:
                delta = r.randint(-max_delta, max_delta)
                out.data[i] = max(0, min(255, out.data[i] + delta))

        return out

    @staticmethod
    def apply_byte_shuffle_glitch(
        frame: ImageFrame,
        chunk_size: int = 64,
        shuffle_count: int = 12,
        rng: Optional[random.Random] = None,
    ) -> ImageFrame:
        """Randomly swap chunks of raw pixel data to simulate framebuffer memory corruption."""
        r = rng or random.Random()
        out = frame.copy()
        total_bytes = len(out.data)
        if total_bytes < chunk_size * 2:
            return out

        max_offset = total_bytes - chunk_size
        for _ in range(shuffle_count):
            pos_a = r.randint(0, max_offset)
            pos_b = r.randint(0, max_offset)
            chunk_a = out.data[pos_a : pos_a + chunk_size]
            chunk_b = out.data[pos_b : pos_b + chunk_size]
            out.data[pos_a : pos_a + chunk_size] = chunk_b
            out.data[pos_b : pos_b + chunk_size] = chunk_a

        return out

    def process_frame(
        self,
        frame: ImageFrame,
        preset: Optional[GlitchPreset] = None,
        previous_frame: Optional[ImageFrame] = None,
        seed: Optional[int] = None
    ) -> ImageFrame:
        """Apply full multi-stage datamosh pipeline to a single frame."""
        p = preset or self.preset
        rng = random.Random(seed) if seed is not None else random.Random()

        # Step 1: Ghosting / Motion trail blend with previous frame
        res = self.apply_ghost_blend(frame, previous_frame, p.ghost_blend)

        # Step 2: Horizontal slice shifts
        res = self.apply_horizontal_slice_shift(res, p.slice_height, p.horizontal_shift_max, rng)

        # Step 3: Vertical block displacements
        res = self.apply_vertical_block_shift(res, p.vertical_block_width, p.vertical_shift_max, rng)

        # Step 4: Macroblock compression corruption
        res = self.apply_macroblock_corruption(res, p.block_artifact_size, p.block_artifact_probability, rng)

        # Step 5: RGB Chromatic Aberration channel split
        res = self.apply_rgb_split(res, p.color_shift_x, p.color_shift_y)

        # Step 6: Scanlines / VCR tracking lines
        res = self.apply_scanlines(res, p.scanline_intensity, p.scanline_frequency)

        # Step 7: Static noise floor
        res = self.apply_noise(res, p.noise_intensity, rng)

        return res

    def process_video_sequence(
        self,
        frames: List[ImageFrame],
        preset: Optional[GlitchPreset] = None,
        seed: Optional[int] = None
    ) -> List[ImageFrame]:
        """Process a sequence of video frames with persistent motion vector accumulation."""
        out_frames: List[ImageFrame] = []
        prev: Optional[ImageFrame] = None
        base_seed = seed or 42

        for idx, f in enumerate(frames):
            frame_seed = base_seed + idx * 7
            processed = self.process_frame(f, preset=preset, previous_frame=prev, seed=frame_seed)
            out_frames.append(processed)
            # Retain glitched frame as reference for next frame's motion smear (I-frame drop)
            prev = processed

        return out_frames


def corrupt_byte_stream(
    raw_bytes: bytes,
    rate: float = 0.002,
    header_skip: int = 64,
    seed: Optional[int] = None
) -> bytes:
    """Directly corrupt binary byte stream (for raw AVI/MP4 or BMP testing) while preserving headers."""
    if rate <= 0.0 or len(raw_bytes) <= header_skip:
        return raw_bytes

    rng = random.Random(seed)
    barr = bytearray(raw_bytes)
    total_corruptible = len(barr) - header_skip
    num_corruptions = max(1, int(total_corruptible * rate))

    for _ in range(num_corruptions):
        pos = rng.randint(header_skip, len(barr) - 1)
        mode = rng.choice(["flip", "zero", "max", "rand"])
        if mode == "flip":
            barr[pos] ^= (1 << rng.randint(0, 7))
        elif mode == "zero":
            barr[pos] = 0
        elif mode == "max":
            barr[pos] = 255
        else:
            barr[pos] = rng.randint(0, 255)

    return bytes(barr)
