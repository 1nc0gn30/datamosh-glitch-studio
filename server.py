#!/usr/bin/env python3
"""
Datamosh Glitch Studio — Sovereign Server Launcher.
Visual Artifact, Motion Vector & Bitplane Glitch Studio on port 8081.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from datamosh_glitch_studio.ui_server import run_ui_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Datamosh Glitch Studio Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=8081, help="Port to listen on (default: 8081)")
    args = parser.parse_args()

    print(f"✦ Starting Datamosh Glitch Studio on http://{args.host}:{args.port}")
    server = run_ui_server(host=args.host, port=args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Datamosh Glitch Studio server...")
        server.server_close()
