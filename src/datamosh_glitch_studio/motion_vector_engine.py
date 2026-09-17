"""
Motion Vector Engine: Macroblock Optical Flow Estimation, I/P-Frame Slicing, and Vector Glitch Operators.
Zero external runtime dependencies (100% Python Standard Library).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from datamosh_glitch_studio.frame_io import ImageFrame


class FrameType(str, Enum):
    IFRAME = "I_FRAME"  # Intra-coded keyframe (full image data)
    PFRAME = "P_FRAME"  # Predicted frame (motion vectors + residual delta)


@dataclass
class MacroblockMotionVector:
    """Motion vector for a single macroblock."""
    mb_x: int  # Block column coordinate in pixels
    mb_y: int  # Block row coordinate in pixels
    dx: int    # Horizontal displacement
    dy: int    # Vertical displacement
    sad: float # Sum of Absolute Differences (match error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mb_x": self.mb_x,
            "mb_y": self.mb_y,
            "dx": self.dx,
            "dy": self.dy,
            "sad": round(self.sad, 2),
        }


@dataclass
class MotionVectorField:
    """Field of motion vectors representing optical displacement across macroblocks."""
    width: int
    height: int
    block_size: int
    vectors: List[MacroblockMotionVector] = field(default_factory=list)
    average_magnitude: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "block_size": self.block_size,
            "total_blocks": len(self.vectors),
            "average_magnitude": round(self.average_magnitude, 3),
            "vectors": [v.to_dict() for v in self.vectors[:50]],  # Truncate sample
        }


@dataclass
class CodedVideoFrame:
    """Structured representation of a video frame with GOP classification."""
    index: int
    frame_type: FrameType
    frame: ImageFrame
    motion_vectors: Optional[MotionVectorField] = None
    residual_energy: float = 0.0


class MotionVectorEngine:
    """Estimates block motion vectors, structures I/P-frames, and synthesizes vector glitches."""

    def __init__(self, block_size: int = 16, search_range: int = 6) -> None:
        self.block_size = block_size
        self.search_range = search_range

    def estimate_motion(
        self,
        reference: ImageFrame,
        target: ImageFrame,
        block_size: Optional[int] = None,
        search_range: Optional[int] = None,
    ) -> MotionVectorField:
        """
        Estimate motion vectors from reference frame to target frame using Block Matching Algorithm.
        Finds the (dx, dy) within search_range that minimizes Sum of Absolute Differences (SAD).
        """
        bs = block_size or self.block_size
        sr = search_range or self.search_range
        w, h = target.width, target.height

        ref_data = reference.data
        tgt_data = target.data

        vectors: List[MacroblockMotionVector] = []
        total_mag = 0.0

        for y in range(0, h, bs):
            for x in range(0, w, bs):
                cur_bw = min(bs, w - x)
                cur_bh = min(bs, h - y)

                best_dx = 0
                best_dy = 0
                best_sad = float("inf")

                # Search candidate displacements in window [-sr, sr]
                for dy in range(-sr, sr + 1):
                    cand_y = y + dy
                    if cand_y < 0 or cand_y + cur_bh > h:
                        continue

                    for dx in range(-sr, sr + 1):
                        cand_x = x + dx
                        if cand_x < 0 or cand_x + cur_bw > w:
                            continue

                        # Compute SAD (Sum of Absolute Differences) between target and reference candidate
                        sad = 0
                        # Sample step of 2 for fast estimation
                        for by in range(0, cur_bh, 2):
                            tgt_row_idx = (y + by) * w * 3 + x * 3
                            ref_row_idx = (cand_y + by) * w * 3 + cand_x * 3
                            for bx in range(0, cur_bw * 3, 6):
                                sad += (
                                    abs(tgt_data[tgt_row_idx + bx] - ref_data[ref_row_idx + bx]) +
                                    abs(tgt_data[tgt_row_idx + bx + 1] - ref_data[ref_row_idx + bx + 1]) +
                                    abs(tgt_data[tgt_row_idx + bx + 2] - ref_data[ref_row_idx + bx + 2])
                                )

                        if sad < best_sad:
                            best_sad = sad
                            best_dx = dx
                            best_dy = dy
                            if sad == 0:
                                break
                    if best_sad == 0:
                        break

                mag = math.hypot(best_dx, best_dy)
                total_mag += mag
                vectors.append(MacroblockMotionVector(
                    mb_x=x,
                    mb_y=y,
                    dx=best_dx,
                    dy=best_dy,
                    sad=best_sad
                ))

        avg_mag = total_mag / len(vectors) if vectors else 0.0
        return MotionVectorField(
            width=w,
            height=h,
            block_size=bs,
            vectors=vectors,
            average_magnitude=avg_mag,
        )

    def apply_motion_vectors(
        self,
        carrier_frame: ImageFrame,
        mv_field: MotionVectorField,
        multiplier: float = 1.0,
        jitter: int = 0,
        rng: Optional[random.Random] = None,
    ) -> ImageFrame:
        """
        Warp carrier_frame pixels using motion vectors.
        This reproduces the classic I-frame drop / bloom datamosh effect.
        """
        r = rng or random.Random(42)
        out = carrier_frame.copy()
        w, h = carrier_frame.width, carrier_frame.height
        bs = mv_field.block_size
        carrier_data = carrier_frame.data
        out_data = out.data

        for mv in mv_field.vectors:
            dx = int(round(mv.dx * multiplier))
            dy = int(round(mv.dy * multiplier))

            if jitter > 0:
                dx += r.randint(-jitter, jitter)
                dy += r.randint(-jitter, jitter)

            if dx == 0 and dy == 0:
                continue

            bx_start = mv.mb_x
            by_start = mv.mb_y
            bw = min(bs, w - bx_start)
            bh = min(bs, h - by_start)

            for by in range(bh):
                src_y = by_start + by + dy
                dst_y = by_start + by
                if not (0 <= src_y < h):
                    continue

                for bx in range(bw):
                    src_x = bx_start + bx + dx
                    dst_x = bx_start + bx
                    if not (0 <= src_x < w):
                        continue

                    src_idx = (src_y * w + src_x) * 3
                    dst_idx = (dst_y * w + dst_x) * 3

                    out_data[dst_idx] = carrier_data[src_idx]
                    out_data[dst_idx + 1] = carrier_data[src_idx + 1]
                    out_data[dst_idx + 2] = carrier_data[src_idx + 2]

        return out

    def datamosh_iframe_kill(
        self,
        scene_a_last_frame: ImageFrame,
        scene_b_frames: List[ImageFrame],
        vector_multiplier: float = 1.5,
    ) -> List[ImageFrame]:
        """
        Classic I-Frame Kill Datamosh:
        Take the final frame of Scene A as the canvas base.
        Strip the keyframe of Scene B, and apply all consecutive Scene B motion vectors
        directly onto the pixels of Scene A, causing Scene A to be dragged and deformed by Scene B.
        """
        if not scene_b_frames:
            return [scene_a_last_frame]

        output_frames: List[ImageFrame] = []
        canvas = scene_a_last_frame.copy()

        # For the first transition frame, compute motion from scene_b[0] to scene_b[1] if available
        # or use synthetic displacement
        prev_scene_b = scene_b_frames[0]
        output_frames.append(canvas.copy())

        for i in range(1, len(scene_b_frames)):
            curr_scene_b = scene_b_frames[i]
            mv_field = self.estimate_motion(prev_scene_b, curr_scene_b)
            # Warp current canvas using Scene B motion
            canvas = self.apply_motion_vectors(canvas, mv_field, multiplier=vector_multiplier)
            output_frames.append(canvas.copy())
            prev_scene_b = curr_scene_b

        return output_frames

    def datamosh_liquid_melt(
        self,
        frame: ImageFrame,
        motion_vector: Tuple[int, int] = (4, 2),
        steps: int = 8,
        acceleration: float = 1.2,
    ) -> List[ImageFrame]:
        """
        Synthesizes a continuous liquid melt by recursively compounding a directional motion vector field.
        """
        w, h = frame.width, frame.height
        bs = self.block_size
        frames: List[ImageFrame] = [frame.copy()]
        current = frame.copy()

        base_dx, base_dy = motion_vector
        cur_dx, cur_dy = float(base_dx), float(base_dy)

        for step in range(steps):
            # Create synthetic motion vector field with subtle spatial wave variation
            vectors: List[MacroblockMotionVector] = []
            for y in range(0, h, bs):
                for x in range(0, w, bs):
                    # Add subtle sinusoidal turbulence
                    turb = math.sin(x * 0.05 + step * 0.8) * 2.0
                    v_dx = int(round(cur_dx + turb))
                    v_dy = int(round(cur_dy))
                    vectors.append(MacroblockMotionVector(mb_x=x, mb_y=y, dx=v_dx, dy=v_dy, sad=0.0))

            mv_field = MotionVectorField(width=w, height=h, block_size=bs, vectors=vectors)
            current = self.apply_motion_vectors(current, mv_field)
            frames.append(current.copy())

            cur_dx *= acceleration
            cur_dy *= acceleration

        return frames

    def compute_residual_delta(self, ref_frame: ImageFrame, target_frame: ImageFrame) -> ImageFrame:
        """Compute visual residual delta difference between two frames."""
        w, h = ref_frame.width, ref_frame.height
        out = ImageFrame.create(w, h, color=(0, 0, 0))
        ref_data = ref_frame.data
        tgt_data = target_frame.data
        out_data = out.data

        for i in range(0, w * h * 3, 3):
            dr = abs(tgt_data[i] - ref_data[i])
            dg = abs(tgt_data[i + 1] - ref_data[i + 1])
            db = abs(tgt_data[i + 2] - ref_data[i + 2])
            # Boost contrast for visualization
            out_data[i] = min(255, dr * 3)
            out_data[i + 1] = min(255, dg * 3)
            out_data[i + 2] = min(255, db * 3)

        return out


def render_motion_vectors_svg(mv_field: MotionVectorField) -> str:
    """Render motion vector arrows as a standalone SVG vector map."""
    w, h = mv_field.width, mv_field.height
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#111;">',
        '<defs>',
        '  <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">',
        '    <path d="M 0 0 L 10 5 L 0 10 z" fill="#00ffcc" />',
        '  </marker>',
        '</defs>',
    ]

    bs = mv_field.block_size
    for mv in mv_field.vectors:
        if mv.dx == 0 and mv.dy == 0:
            continue
        cx = mv.mb_x + bs // 2
        cy = mv.mb_y + bs // 2
        target_x = cx + mv.dx * 3
        target_y = cy + mv.dy * 3

        svg_parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{target_x}" y2="{target_y}" stroke="#00ffcc" stroke-width="1.5" marker-end="url(#arrow)" />'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def render_motion_vectors_ascii(mv_field: MotionVectorField, max_cols: int = 40) -> str:
    """Render a compact 2D ASCII grid of arrow directions representing optical flow."""
    w, h = mv_field.width, mv_field.height
    bs = mv_field.block_size
    cols = max(1, w // bs)
    rows = max(1, h // bs)

    grid: Dict[Tuple[int, int], str] = {}
    for mv in mv_field.vectors:
        col = mv.mb_x // bs
        row = mv.mb_y // bs
        dx, dy = mv.dx, mv.dy
        if dx == 0 and dy == 0:
            sym = "·"
        elif dx > 0 and dy == 0:
            sym = "→"
        elif dx < 0 and dy == 0:
            sym = "←"
        elif dx == 0 and dy > 0:
            sym = "↓"
        elif dx == 0 and dy < 0:
            sym = "↑"
        elif dx > 0 and dy > 0:
            sym = "↘"
        elif dx > 0 and dy < 0:
            sym = "↗"
        elif dx < 0 and dy > 0:
            sym = "↙"
        else:
            sym = "↖"
        grid[(col, row)] = sym

    lines = []
    for r in range(rows):
        line = "".join(grid.get((c, r), " ") for c in range(min(cols, max_cols)))
        lines.append(line)

    return "\n".join(lines)
