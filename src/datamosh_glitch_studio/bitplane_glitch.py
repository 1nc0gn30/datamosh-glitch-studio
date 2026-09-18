"""Bitplane Glitch Engine, Slicer, and Spatial XOR Synthesizer for datamosh-glitch-studio.

Performs 8-bit channel bitplane decomposition (Bit 0 LSB to Bit 7 MSB), selective bitplane
isolation/slicing, bit inversion/solarization, cross-channel bit swapping, Bayer matrix ordered
dithering, and fractal Sierpiński spatial XOR synthesis.

100% Python Standard Library. Zero third-party runtime dependencies.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union

from datamosh_glitch_studio.frame_io import ImageFrame


# 4x4 Bayer dithering matrix (normalized values 0..15 scaled to 0..255)
BAYER_4X4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]


class BitplaneExtractor:
    """Decomposes 24-bit RGB frames into 8 binary bitplane layers."""

    @staticmethod
    def extract_bitplane(
        frame: ImageFrame,
        bit: int,
        channel: str = "all",
    ) -> ImageFrame:
        """Extract a single bitplane (0 = LSB, 7 = MSB) as a binary visualization frame.

        Args:
            frame: Input ImageFrame.
            bit: Bit index (0 to 7).
            channel: 'r', 'g', 'b', 'all', or 'luminance'.

        Returns:
            Binary ImageFrame where active bits are 255 and inactive are 0.
        """
        if not (0 <= bit <= 7):
            raise ValueError(f"Bit index must be 0..7, got {bit}")

        mask = 1 << bit
        out = ImageFrame.create(frame.width, frame.height)
        ch = channel.lower()

        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b = frame.get_pixel(x, y)
                if ch == "luminance":
                    lum = int(0.299 * r + 0.587 * g + 0.114 * b)
                    val = 255 if (lum & mask) else 0
                    out.set_pixel(x, y, (val, val, val))
                elif ch == "r":
                    val = 255 if (r & mask) else 0
                    out.set_pixel(x, y, (val, 0, 0))
                elif ch == "g":
                    val = 255 if (g & mask) else 0
                    out.set_pixel(x, y, (0, val, 0))
                elif ch == "b":
                    val = 255 if (b & mask) else 0
                    out.set_pixel(x, y, (0, 0, val))
                else:  # "all"
                    or_val = 255 if (r & mask) else 0
                    og_val = 255 if (g & mask) else 0
                    ob_val = 255 if (b & mask) else 0
                    out.set_pixel(x, y, (or_val, og_val, ob_val))

        return out

    @classmethod
    def extract_all_bitplanes(
        cls,
        frame: ImageFrame,
        channel: str = "luminance",
    ) -> List[ImageFrame]:
        """Extract all 8 bitplanes from Bit 0 (LSB) to Bit 7 (MSB)."""
        return [cls.extract_bitplane(frame, bit=b, channel=channel) for b in range(8)]


class BitplaneGlitchEngine:
    """Applies bit-level logic, bitplane permutation, and spatial XOR glitch syntheses."""

    @staticmethod
    def slice_bitplanes(
        frame: ImageFrame,
        keep_bits: List[int],
        channel: str = "all",
    ) -> ImageFrame:
        """Mask out all bitplanes except those specified in keep_bits.

        Args:
            frame: Input ImageFrame.
            keep_bits: List of bit indices to preserve (0..7). E.g. [7, 6] preserves the two MSBs.
            channel: 'r', 'g', 'b', or 'all'.
        """
        mask = 0
        for b in keep_bits:
            if 0 <= b <= 7:
                mask |= (1 << b)

        ch = channel.lower()
        out = frame.copy()

        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b = frame.get_pixel(x, y)
                nr = (r & mask) if ch in ("all", "r") else r
                ng = (g & mask) if ch in ("all", "g") else g
                nb = (b & mask) if ch in ("all", "b") else b
                out.set_pixel(x, y, (nr, ng, nb))

        return out

    @staticmethod
    def invert_bitplanes(
        frame: ImageFrame,
        invert_bits: List[int],
        channel: str = "all",
    ) -> ImageFrame:
        """Invert specified bitplanes to produce digital solarization and chromatic folds.

        Args:
            frame: Input ImageFrame.
            invert_bits: List of bit indices to flip (0..7). E.g. [7] flips the MSB.
            channel: 'r', 'g', 'b', or 'all'.
        """
        mask = 0
        for b in invert_bits:
            if 0 <= b <= 7:
                mask |= (1 << b)

        ch = channel.lower()
        out = frame.copy()

        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b = frame.get_pixel(x, y)
                nr = (r ^ mask) if ch in ("all", "r") else r
                ng = (g ^ mask) if ch in ("all", "g") else g
                nb = (b ^ mask) if ch in ("all", "b") else b
                out.set_pixel(x, y, (nr, ng, nb))

        return out

    @staticmethod
    def permute_bitplanes(
        frame: ImageFrame,
        permutation: Dict[int, int],
        channel: str = "all",
    ) -> ImageFrame:
        """Permute bitplane positions according to a mapping {target_bit: source_bit}.

        Example: {7: 0, 0: 7} swaps the MSB and LSB.
        """
        ch = channel.lower()
        out = frame.copy()

        def _permute_byte(val: int) -> int:
            new_val = val
            for dst, src in permutation.items():
                if 0 <= dst <= 7 and 0 <= src <= 7:
                    bit_val = (val >> src) & 1
                    if bit_val:
                        new_val |= (1 << dst)
                    else:
                        new_val &= ~(1 << dst)
            return new_val

        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b = frame.get_pixel(x, y)
                nr = _permute_byte(r) if ch in ("all", "r") else r
                ng = _permute_byte(g) if ch in ("all", "g") else g
                nb = _permute_byte(b) if ch in ("all", "b") else b
                out.set_pixel(x, y, (nr, ng, nb))

        return out

    @staticmethod
    def channel_bit_swap(
        frame: ImageFrame,
        src_channel: str,
        src_bit: int,
        dst_channel: str,
        dst_bit: int,
    ) -> ImageFrame:
        """Swap bitplane between two distinct color channels (e.g. Red Bit 7 with Blue Bit 6)."""
        src_ch = src_channel.lower()
        dst_ch = dst_channel.lower()
        valid = ("r", "g", "b")
        if src_ch not in valid or dst_ch not in valid:
            raise ValueError(f"Channels must be 'r', 'g', or 'b', got {src_channel} and {dst_channel}")

        out = frame.copy()
        s_mask = 1 << src_bit
        d_mask = 1 << dst_bit

        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b = frame.get_pixel(x, y)
                ch_map = {"r": r, "g": g, "b": b}

                s_val = (ch_map[src_ch] >> src_bit) & 1
                d_val = (ch_map[dst_ch] >> dst_bit) & 1

                # Update src channel with d_val
                if d_val:
                    ch_map[src_ch] |= s_mask
                else:
                    ch_map[src_ch] &= ~s_mask

                # Update dst channel with s_val
                if s_val:
                    ch_map[dst_ch] |= d_mask
                else:
                    ch_map[dst_ch] &= ~d_mask

                out.set_pixel(x, y, (ch_map["r"], ch_map["g"], ch_map["b"]))

        return out

    @staticmethod
    def xor_sierpinski_glitch(
        frame: ImageFrame,
        scale: float = 1.0,
        blend: float = 0.5,
        formula: str = "xor",
    ) -> ImageFrame:
        """Synthesize spatial boolean textures (Sierpiński carpet X xor Y) modulated over frame pixels.

        Args:
            frame: Input ImageFrame.
            scale: Spatial coordinate frequency scale factor.
            blend: Modulation mix factor (0.0 = original, 1.0 = full fractal texture).
            formula: 'xor', 'and', 'or', or 'xor_and'.
        """
        out = frame.copy()
        formula = formula.lower()
        sc = max(0.01, scale)
        b_amt = max(0.0, min(1.0, blend))

        for y in range(frame.height):
            for x in range(frame.width):
                sx = int(x * sc)
                sy = int(y * sc)

                if formula == "and":
                    pat = (sx & sy) % 256
                elif formula == "or":
                    pat = (sx | sy) % 256
                elif formula == "xor_and":
                    pat = ((sx ^ sy) & (sx + sy)) % 256
                else:  # "xor"
                    pat = (sx ^ sy) % 256

                r, g, b = frame.get_pixel(x, y)
                nr = int((1.0 - b_amt) * r + b_amt * (r ^ pat))
                ng = int((1.0 - b_amt) * g + b_amt * (g ^ pat))
                nb = int((1.0 - b_amt) * b + b_amt * (b ^ pat))
                out.set_pixel(x, y, (nr, ng, nb))

        return out

    @staticmethod
    def ordered_dither_glitch(
        frame: ImageFrame,
        levels: int = 4,
    ) -> ImageFrame:
        """Apply 4x4 Bayer matrix ordered dithering with bit-depth quantization.

        Args:
            frame: Input ImageFrame.
            levels: Number of quantization levels per channel (e.g. 2, 4, 8).
        """
        out = frame.copy()
        step = 255.0 / max(1, levels - 1)

        for y in range(frame.height):
            for x in range(frame.width):
                threshold = (BAYER_4X4[y % 4][x % 4] / 16.0 - 0.5) * step
                r, g, b = frame.get_pixel(x, y)

                nr = int(round(max(0.0, min(255.0, r + threshold)) / step) * step)
                ng = int(round(max(0.0, min(255.0, g + threshold)) / step) * step)
                nb = int(round(max(0.0, min(255.0, b + threshold)) / step) * step)
                out.set_pixel(x, y, (nr, ng, nb))

        return out

    @classmethod
    def render_bitplane_mosaic_svg(
        cls,
        frame: ImageFrame,
        channel: str = "luminance",
    ) -> str:
        """Generate a standalone SVG showing a 4x2 matrix of all 8 bitplanes with statistics."""
        bitplanes = BitplaneExtractor.extract_all_bitplanes(frame, channel=channel)
        thumb_w = 120
        thumb_h = int(thumb_w * (frame.height / frame.width))
        padding = 16
        cell_w = thumb_w + padding
        cell_h = thumb_h + 40
        svg_w = cell_w * 4 + padding
        svg_h = cell_h * 2 + 60

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}" style="background: #0d1117; font-family: -apple-system, monospace;">',
            f'<text x="{padding}" y="30" fill="#00ffcc" font-size="16" font-weight="bold">Bitplane Glitch Decomposition Matrix (Channel: {channel.upper()})</text>',
        ]

        for bit in range(8):
            col = bit % 4
            row = bit // 4
            x_pos = padding + col * cell_w
            y_pos = 50 + row * cell_h

            bp_frame = bitplanes[bit]
            # Calculate active pixel ratio
            active_cnt = 0
            total_px = frame.width * frame.height
            for py in range(frame.height):
                for px in range(frame.width):
                    if bp_frame.get_pixel(px, py)[0] > 0:
                        active_cnt += 1
            ratio = (active_cnt / total_px) * 100.0 if total_px > 0 else 0.0

            # Generate SVG image data URI using base64 BMP
            b64_bmp = bp_frame.to_data_uri("bmp")

            label = f"Bit {bit} ({'MSB' if bit == 7 else ('LSB' if bit == 0 else f'2^{bit}')})"
            stat_text = f"{ratio:.1f}% Active"

            svg_parts.append(f'<g transform="translate({x_pos}, {y_pos})">')
            svg_parts.append(f'<rect width="{thumb_w}" height="{thumb_h}" fill="#000" stroke="#30363d" rx="4"/>')
            svg_parts.append(f'<image href="{b64_bmp}" width="{thumb_w}" height="{thumb_h}" preserveAspectRatio="none"/>')
            svg_parts.append(f'<text x="0" y="{thumb_h + 16}" fill="#e6edf3" font-size="11" font-weight="600">{label}</text>')
            svg_parts.append(f'<text x="0" y="{thumb_h + 30}" fill="#8b949e" font-size="10">{stat_text}</text>')
            svg_parts.append('</g>')

        svg_parts.append('</svg>')
        return "\n".join(svg_parts)
