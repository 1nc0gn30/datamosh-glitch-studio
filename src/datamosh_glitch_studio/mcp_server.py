"""
Model Context Protocol (MCP) Server for datamosh-glitch-studio.
Conforms to MCP protocol version 2024-11-05 and JSON-RPC 2.0 over stdio.
Zero external runtime dependencies.
"""

from __future__ import annotations

import base64
import json
import math
import os
import platform
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from datamosh_glitch_studio.bitplane_glitch import (
    BitplaneExtractor,
    BitplaneGlitchEngine,
)
from datamosh_glitch_studio.frame_io import ImageFrame, export_frame_sequence_html
from datamosh_glitch_studio.glitch_core import DatamoshEngine, corrupt_byte_stream
from datamosh_glitch_studio.motion_vector_engine import (
    MotionVectorEngine,
    render_motion_vectors_ascii,
    render_motion_vectors_svg,
)
from datamosh_glitch_studio.presets import PRESETS, GlitchPreset, get_preset, list_presets

SERVER_NAME = "datamosh-glitch-studio"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


class MCPServer:
    """Model Context Protocol stdio server implementation."""

    def __init__(self) -> None:
        self.engine = DatamoshEngine()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return registered MCP tool schemas."""
        return [
            {
                "name": "datamosh_apply",
                "description": "Apply parametric datamosh and glitch effects (slice shift, block displacement, RGB split, scanlines, ghosting) to an image or procedural test pattern.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "preset": {
                            "type": "string",
                            "enum": list(PRESETS.keys()),
                            "default": "h264_iframe_drop",
                            "description": "Glitch preset profile."
                        },
                        "image_base64": {
                            "type": "string",
                            "description": "Optional Base64-encoded 24-bit BMP/PPM image. If omitted, procedural test card is generated."
                        },
                        "width": {
                            "type": "integer",
                            "default": 320,
                            "description": "Width for generated test card (if image_base64 not supplied)."
                        },
                        "height": {
                            "type": "integer",
                            "default": 240,
                            "description": "Height for generated test card."
                        },
                        "seed": {
                            "type": "integer",
                            "description": "Random seed for reproducible glitch patterns."
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["bmp", "ppm"],
                            "default": "bmp",
                            "description": "Output image format."
                        }
                    }
                }
            },
            {
                "name": "datamosh_generate_sequence",
                "description": "Generate a multi-frame video glitch sequence demonstrating continuous I-frame drop and motion vector smearing.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "frame_count": {
                            "type": "integer",
                            "default": 8,
                            "minimum": 2,
                            "maximum": 30,
                            "description": "Number of consecutive glitched frames to generate."
                        },
                        "preset": {
                            "type": "string",
                            "enum": list(PRESETS.keys()),
                            "default": "h264_iframe_drop"
                        },
                        "fps": {
                            "type": "integer",
                            "default": 15
                        }
                    }
                }
            },
            {
                "name": "datamosh_presets",
                "description": "List all available glitch and datamosh presets with their algorithmic parameters.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "datamosh_corrupt_bytes",
                "description": "Directly corrupt a binary byte stream using bitflips, zeroing, and byte injection while preserving headers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "data_base64": {
                            "type": "string",
                            "description": "Base64 encoded binary payload."
                        },
                        "rate": {
                            "type": "number",
                            "default": 0.002,
                            "description": "Corruption rate (ratio of bytes to alter)."
                        },
                        "header_skip": {
                            "type": "integer",
                            "default": 64,
                            "description": "Number of header bytes to protect from corruption."
                        }
                    },
                    "required": ["data_base64"]
                }
            },
            {
                "name": "datamosh_motion_estimate",
                "description": "Perform macroblock optical flow motion estimation, calculate displacement vectors, and render SVG/ASCII vector maps.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "width": {
                            "type": "integer",
                            "default": 160
                        },
                        "height": {
                            "type": "integer",
                            "default": 120
                        },
                        "block_size": {
                            "type": "integer",
                            "default": 16
                        },
                        "shift_dx": {
                            "type": "integer",
                            "default": 4
                        },
                        "shift_dy": {
                            "type": "integer",
                            "default": 2
                        }
                    }
                }
            },
            {
                "name": "datamosh_liquid_melt",
                "description": "Synthesize liquid melting datamosh effect by compounding macroblock motion vectors across multiple frames.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "integer",
                            "default": 6
                        },
                        "width": {
                            "type": "integer",
                            "default": 160
                        },
                        "height": {
                            "type": "integer",
                            "default": 120
                        },
                        "acceleration": {
                            "type": "number",
                            "default": 1.2
                        }
                    }
                }
            },
            {
                "name": "datamosh_bitplane_slice",
                "description": "Decompose 8-bit color channels and selectively isolate or invert bitplanes (0 LSB to 7 MSB) for posterization and solarization glitch effects.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keep_bits": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "default": [7, 6, 5],
                            "description": "Bitplane indices to preserve (0..7)."
                        },
                        "invert_bits": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "default": [],
                            "description": "Bitplane indices to invert/flip."
                        },
                        "channel": {
                            "type": "string",
                            "enum": ["all", "r", "g", "b"],
                            "default": "all",
                            "description": "Color channel to slice."
                        },
                        "image_base64": {
                            "type": "string",
                            "description": "Optional Base64-encoded image. If omitted, procedural color card is used."
                        },
                        "width": {
                            "type": "integer",
                            "default": 320
                        },
                        "height": {
                            "type": "integer",
                            "default": 240
                        }
                    }
                }
            },
            {
                "name": "datamosh_sierpinski_xor",
                "description": "Synthesize fractal spatial boolean glitch textures (XOR, AND, OR) modulated over pixel coordinates.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "formula": {
                            "type": "string",
                            "enum": ["xor", "and", "or", "xor_and"],
                            "default": "xor"
                        },
                        "scale": {
                            "type": "number",
                            "default": 1.0
                        },
                        "blend": {
                            "type": "number",
                            "default": 0.5
                        },
                        "image_base64": {
                            "type": "string"
                        },
                        "width": {
                            "type": "integer",
                            "default": 320
                        },
                        "height": {
                            "type": "integer",
                            "default": 240
                        }
                    }
                }
            },
            {
                "name": "datamosh_bitplane_mosaic",
                "description": "Generate an 8-panel SVG mosaic displaying all bitplanes from Bit 0 (LSB) to Bit 7 (MSB) with activity statistics.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "enum": ["luminance", "r", "g", "b", "all"],
                            "default": "luminance"
                        },
                        "image_base64": {
                            "type": "string"
                        },
                        "width": {
                            "type": "integer",
                            "default": 320
                        },
                        "height": {
                            "type": "integer",
                            "default": 240
                        }
                    }
                }
            },
            {
                "name": "datamosh_diagnostics",
                "description": "Run environment, platform, and glitch engine diagnostics.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def _generate_test_card(self, width: int = 320, height: int = 240) -> ImageFrame:
        """Create standard SMPTE-style RGB color bars test pattern."""
        frame = ImageFrame.create(width, height)
        colors = [
            (255, 255, 255),  # White
            (255, 255, 0),    # Yellow
            (0, 255, 255),    # Cyan
            (0, 255, 0),      # Green
            (255, 0, 255),    # Magenta
            (255, 0, 0),      # Red
            (0, 0, 255),      # Blue
            (20, 20, 20),     # Dark
        ]
        bar_w = width // len(colors)
        for y in range(height):
            for x in range(width):
                c_idx = min(len(colors) - 1, x // bar_w)
                frame.set_pixel(x, y, colors[c_idx])
        return frame

    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool and format MCP result."""
        if tool_name == "datamosh_apply":
            preset_name = arguments.get("preset", "h264_iframe_drop")
            preset = get_preset(preset_name)
            img_b64 = arguments.get("image_base64")
            seed = arguments.get("seed")
            out_fmt = arguments.get("output_format", "bmp")

            if img_b64:
                raw_img = base64.b64decode(img_b64)
                if raw_img.startswith(b"BM"):
                    frame = ImageFrame.from_bmp(raw_img)
                elif raw_img.startswith(b"P6"):
                    frame = ImageFrame.from_ppm(raw_img)
                else:
                    raise ValueError("Unsupported input format (must be BMP or P6 PPM)")
            else:
                w = arguments.get("width", 320)
                h = arguments.get("height", 240)
                frame = self._generate_test_card(w, h)

            glitched = self.engine.process_frame(frame, preset=preset, seed=seed)
            out_bytes = glitched.to_bmp() if out_fmt == "bmp" else glitched.to_ppm()
            res_b64 = base64.b64encode(out_bytes).decode("ascii")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "success",
                            "preset": preset.name,
                            "width": glitched.width,
                            "height": glitched.height,
                            "format": out_fmt,
                            "size_bytes": len(out_bytes),
                            "image_base64": res_b64
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_generate_sequence":
            count = arguments.get("frame_count", 8)
            preset_name = arguments.get("preset", "h264_iframe_drop")
            preset = get_preset(preset_name)

            # Generate dynamic test card sequence
            base_frames = []
            for i in range(count):
                f = self._generate_test_card(240, 180)
                # Animate a bouncing box
                bx = int(120 + 80 * math.sin(i * 0.5))
                by = int(90 + 50 * math.cos(i * 0.5))
                for dy in range(-20, 20):
                    for dx in range(-20, 20):
                        f.set_pixel(bx + dx, by + dy, (255, 255, 255))
                base_frames.append(f)

            glitched_seq = self.engine.process_video_sequence(base_frames, preset=preset)
            b64_frames = [base64.b64encode(f.to_bmp()).decode("ascii") for f in glitched_seq]

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "success",
                            "preset": preset.name,
                            "frame_count": len(glitched_seq),
                            "dimensions": {"width": 240, "height": 180},
                            "frames_base64": b64_frames
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_presets":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"presets": list_presets()}, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_corrupt_bytes":
            data_b64 = arguments["data_base64"]
            rate = float(arguments.get("rate", 0.002))
            hdr_skip = int(arguments.get("header_skip", 64))
            raw = base64.b64decode(data_b64)
            corrupted = corrupt_byte_stream(raw, rate=rate, header_skip=hdr_skip)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "success",
                            "original_length": len(raw),
                            "corrupted_length": len(corrupted),
                            "corrupted_base64": base64.b64encode(corrupted).decode("ascii")
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_motion_estimate":
            w = int(arguments.get("width", 160))
            h = int(arguments.get("height", 120))
            bs = int(arguments.get("block_size", 16))
            shift_dx = int(arguments.get("shift_dx", 4))
            shift_dy = int(arguments.get("shift_dy", 2))

            ref = self._generate_test_card(w, h)
            # Create target with synthetic displacement
            tgt = ImageFrame.create(w, h)
            for y in range(h):
                for x in range(w):
                    src_x = (x - shift_dx) % w
                    src_y = (y - shift_dy) % h
                    tgt.set_pixel(x, y, ref.get_pixel(src_x, src_y))

            mv_engine = MotionVectorEngine(block_size=bs)
            mv_field = mv_engine.estimate_motion(ref, tgt)
            svg_map = render_motion_vectors_svg(mv_field)
            ascii_map = render_motion_vectors_ascii(mv_field)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "width": w,
                            "height": h,
                            "block_size": bs,
                            "total_blocks": len(mv_field.vectors),
                            "average_magnitude": round(mv_field.average_magnitude, 3),
                            "ascii_flow_grid": ascii_map,
                            "svg_vector_map": svg_map,
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_liquid_melt":
            w = int(arguments.get("width", 160))
            h = int(arguments.get("height", 120))
            steps = int(arguments.get("steps", 6))
            acc = float(arguments.get("acceleration", 1.2))

            ref = self._generate_test_card(w, h)
            mv_engine = MotionVectorEngine(block_size=16)
            frames = mv_engine.datamosh_liquid_melt(ref, steps=steps, acceleration=acc)
            html_bundle = export_frame_sequence_html(frames, fps=12)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "success",
                            "frames_count": len(frames),
                            "width": w,
                            "height": h,
                            "html_animation_bytes": len(html_bundle),
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_bitplane_slice":
            keep_bits = arguments.get("keep_bits", [7, 6, 5])
            invert_bits = arguments.get("invert_bits", [])
            channel = arguments.get("channel", "all")
            img_b64 = arguments.get("image_base64")

            if img_b64:
                raw_img = base64.b64decode(img_b64)
                frame = ImageFrame.from_bmp(raw_img) if raw_img.startswith(b"BM") else ImageFrame.from_ppm(raw_img)
            else:
                w = int(arguments.get("width", 320))
                h = int(arguments.get("height", 240))
                frame = self._generate_test_card(w, h)

            sliced = BitplaneGlitchEngine.slice_bitplanes(frame, keep_bits=keep_bits, channel=channel)
            if invert_bits:
                sliced = BitplaneGlitchEngine.invert_bitplanes(sliced, invert_bits=invert_bits, channel=channel)

            bmp_bytes = sliced.to_bmp()
            res_b64 = base64.b64encode(bmp_bytes).decode("ascii")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "success",
                            "keep_bits": keep_bits,
                            "invert_bits": invert_bits,
                            "channel": channel,
                            "width": sliced.width,
                            "height": sliced.height,
                            "image_base64": res_b64,
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_sierpinski_xor":
            scale = float(arguments.get("scale", 1.0))
            blend = float(arguments.get("blend", 0.5))
            formula = str(arguments.get("formula", "xor"))
            img_b64 = arguments.get("image_base64")

            if img_b64:
                raw_img = base64.b64decode(img_b64)
                frame = ImageFrame.from_bmp(raw_img) if raw_img.startswith(b"BM") else ImageFrame.from_ppm(raw_img)
            else:
                w = int(arguments.get("width", 320))
                h = int(arguments.get("height", 240))
                frame = self._generate_test_card(w, h)

            glitched = BitplaneGlitchEngine.xor_sierpinski_glitch(frame, scale=scale, blend=blend, formula=formula)
            bmp_bytes = glitched.to_bmp()
            res_b64 = base64.b64encode(bmp_bytes).decode("ascii")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "success",
                            "formula": formula,
                            "scale": scale,
                            "blend": blend,
                            "width": glitched.width,
                            "height": glitched.height,
                            "image_base64": res_b64,
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_bitplane_mosaic":
            channel = str(arguments.get("channel", "luminance"))
            img_b64 = arguments.get("image_base64")

            if img_b64:
                raw_img = base64.b64decode(img_b64)
                frame = ImageFrame.from_bmp(raw_img) if raw_img.startswith(b"BM") else ImageFrame.from_ppm(raw_img)
            else:
                w = int(arguments.get("width", 320))
                h = int(arguments.get("height", 240))
                frame = self._generate_test_card(w, h)

            svg_mosaic = BitplaneGlitchEngine.render_bitplane_mosaic_svg(frame, channel=channel)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "success",
                            "channel": channel,
                            "width": frame.width,
                            "height": frame.height,
                            "svg_mosaic": svg_mosaic,
                        }, indent=2)
                    }
                ]
            }

        elif tool_name == "datamosh_diagnostics":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "server": SERVER_NAME,
                            "version": SERVER_VERSION,
                            "protocol_version": PROTOCOL_VERSION,
                            "platform": sys.platform,
                            "python_version": sys.version,
                            "presets_loaded": len(PRESETS),
                            "zero_dependencies": True,
                            "status": "HEALTHY"
                        }, indent=2)
                    }
                ]
            }

        raise ValueError(f"Unknown tool: {tool_name}")

    def handle_request(self, request_str: str) -> Optional[str]:
        """Process JSON-RPC 2.0 request string and return formatted response."""
        try:
            req = json.loads(request_str)
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            })

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}
                }
            })

        elif method == "notifications/initialized":
            return None

        elif method == "ping":
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}})

        elif method == "tools/list":
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.get_tool_definitions()}
            })

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                res = self.handle_tool_call(name, arguments)
                return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": res})
            except Exception as e:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                })

        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        })

    def run_stdio(self) -> None:
        """Run stdio loop reading JSON-RPC requests."""
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            resp = self.handle_request(line_str)
            if resp:
                sys.stdout.write(resp + "\n")
                sys.stdout.flush()


def run_mcp_server() -> None:
    """Entrypoint to launch MCP stdio server."""
    server = MCPServer()
    server.run_stdio()
