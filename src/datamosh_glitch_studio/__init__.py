"""
datamosh-glitch-studio: Parametric Datamosh, I-Frame Drop & Visual Glitch Synthesis Studio.
Zero external runtime dependencies.
"""

from __future__ import annotations

from datamosh_glitch_studio.bitplane_glitch import (
    BitplaneExtractor,
    BitplaneGlitchEngine,
)
from datamosh_glitch_studio.frame_io import ImageFrame, export_frame_sequence_html
from datamosh_glitch_studio.glitch_core import DatamoshEngine, corrupt_byte_stream
from datamosh_glitch_studio.mcp_server import MCPServer, run_mcp_server
from datamosh_glitch_studio.motion_vector_engine import (
    FrameType,
    MacroblockMotionVector,
    MotionVectorEngine,
    MotionVectorField,
    render_motion_vectors_ascii,
    render_motion_vectors_svg,
)
from datamosh_glitch_studio.presets import (
    GlitchPreset,
    get_preset,
    list_presets,
    modulate_preset_with_audio,
)

__version__ = "0.1.0"
__author__ = "1nc0gn30"
__all__ = [
    "ImageFrame",
    "DatamoshEngine",
    "BitplaneExtractor",
    "BitplaneGlitchEngine",
    "GlitchPreset",
    "get_preset",
    "list_presets",
    "modulate_preset_with_audio",
    "corrupt_byte_stream",
    "export_frame_sequence_html",
    "FrameType",
    "MacroblockMotionVector",
    "MotionVectorField",
    "MotionVectorEngine",
    "render_motion_vectors_svg",
    "render_motion_vectors_ascii",
    "MCPServer",
    "run_mcp_server",
]
