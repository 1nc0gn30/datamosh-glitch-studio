# 📼 Datamosh Glitch Studio

[![CI](https://github.com/1nc0gn30/datamosh-glitch-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/1nc0gn30/datamosh-glitch-studio/actions)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0%20runtime-success.svg)](https://github.com/1nc0gn30/datamosh-glitch-studio)
[![MCP Server](https://img.shields.io/badge/MCP-FastMCP%202024--11--05-blueviolet.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Parametric Datamosh, I-Frame Drop & Visual Glitch Synthesis Studio with Material 3 Web UI, Multi-OS CLI, FastMCP stdio server, and zero external runtime dependencies.**

---

## ✨ Features

- 📼 **Parametric Datamosh Engine**: Simulates authentic H.264 I-frame drops, P-frame motion vector smearing, RGB chromatic aberration channel splits, macroblock corruption, CRT/VCR scanlines, and sensor noise.
- 🎨 **Google Material 3 Light Mode Web UI**: Real-time glitch parameter controls, live canvas rendering, preset switcher, webcam stream moshing, and instant BMP frame export.
- ⚡ **Zero Third-Party Runtime Dependencies**: 100% Python Standard Library implementation (`struct`, `io`, `http.server`, `urllib`, `random`, `math`, `dataclasses`).
- 🤖 **FastMCP Server Protocol**: Full Model Context Protocol (MCP) JSON-RPC 2.0 stdio server for Claude Desktop, Cursor, Cline, and autonomous AI agents.
- 💻 **Cross-Platform CLI**: Complete multi-OS command-line interface with `--no-color` support, reproducible seeds, and batch processing.
- 🖼️ **Pure Python Codecs**: Built-in 24-bit/32-bit Windows BMP and Netpbm PPM (P6) binary decoders and encoders.

---

## 🚀 Quick Start

### Installation
```bash
# Clone the repository
git clone https://github.com/1nc0gn30/datamosh-glitch-studio.git
cd datamosh-glitch-studio

# Install in editable mode
pip install -e .
```

---

## 💻 CLI Usage

```bash
# Apply classic I-frame drop glitch to test card
datamosh-studio mosh -p h264_iframe_drop -o glitched.bmp

# Apply Cyberpunk VCR glitch to custom BMP image with reproducible seed
datamosh-studio mosh input.bmp -p cyberpunk_vcr --seed 1337 -o vcr_glitch.bmp

# List available glitch presets
datamosh-studio presets

# Corrupt binary stream with bitflips while preserving 64-byte headers
datamosh-studio corrupt payload.bin --rate 0.005 -o corrupted.bin

# Launch Google Material 3 Studio Web UI
datamosh-studio serve --port 8098

# Start FastMCP stdio server for LLM agents
datamosh-studio mcp

# Run system diagnostics
datamosh-studio doctor
```

---

## 🎨 Presets Catalog

| Preset ID | Name | Core Aesthetic & Mechanics |
| :--- | :--- | :--- |
| `h264_iframe_drop` | **H.264 I-Frame Drop** | Missing keyframe compression artifacts, macroblock drag, motion smearing |
| `cyberpunk_vcr` | **Cyberpunk VCR Tracking** | Magnetic tape tracking errors, horizontal scanline roll, chromatic displacement |
| `rgb_split_overdrive` | **RGB Aberration Overdrive**| Extreme spatial separation of Red, Green, and Blue color channels |
| `analog_tape_decay` | **Analog Tape Decay** | Degraded magnetic tape, high noise floor, intermittent dropouts |
| `quantum_matrix_tear` | **Quantum Matrix Tear** | High-frequency macroblock corruption, payload bitflips, byte displacement |

---

## 🤖 Model Context Protocol (MCP) Setup

Add `datamosh-glitch-studio` to your Claude Desktop or Cursor configuration:

```json
{
  "mcpServers": {
    "datamosh-studio": {
      "command": "python3",
      "args": ["-m", "datamosh_glitch_studio", "mcp"]
    }
  }
}
```

### Registered MCP Tools:
- `datamosh_apply`: Apply glitch effects to Base64 image or procedural test pattern.
- `datamosh_generate_sequence`: Generate multi-frame animation demonstrating continuous I-frame motion smear.
- `datamosh_presets`: Query all presets and algorithmic parameters.
- `datamosh_corrupt_bytes`: Directly corrupt binary payloads with bitflips and noise.
- `datamosh_diagnostics`: Platform and engine health check.

---

## 🧪 Running Tests

```bash
pytest -v
```

---

## 📜 License

MIT License © 2026 1nc0gn30
