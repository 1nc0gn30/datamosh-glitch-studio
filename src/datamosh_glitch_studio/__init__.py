"""
datamosh-glitch-studio: Parametric Datamosh, I-Frame Drop & Visual Glitch Synthesis Studio.
Zero external runtime dependencies.
"""

from __future__ import annotations

from datamosh_glitch_studio.frame_io import ImageFrame, export_frame_sequence_html
from datamosh_glitch_studio.glitch_core import DatamoshEngine, corrupt_byte_stream
from datamosh_glitch_studio.mcp_server import MCPServer, run_mcp_server
from datamosh_glitch_studio.presets import GlitchPreset, get_preset, list_presets

__version__ = "0.1.0"
__author__ = "1nc0gn30"
__all__ = [
    "ImageFrame",
    "DatamoshEngine",
    "GlitchPreset",
    "get_preset",
    "list_presets",
    "corrupt_byte_stream",
    "export_frame_sequence_html",
    "MCPServer",
    "run_mcp_server",
]
