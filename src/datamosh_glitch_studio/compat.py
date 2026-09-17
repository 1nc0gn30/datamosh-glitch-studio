"""
Cross-platform compatibility utilities for datamosh-glitch-studio.
Supports Linux, macOS, Windows, Termux, and WSL.
Zero external runtime dependencies (100% Python Standard Library).
"""

from __future__ import annotations

import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Platform detection flags
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
IS_TERMUX = "TERMUX_VERSION" in os.environ or "com.termux" in os.environ.get("PREFIX", "")


def normalize_path(path: Union[str, Path]) -> Path:
    """Normalize and resolve path safely across operating systems."""
    p = Path(path).expanduser()
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def ensure_dir(path: Union[str, Path]) -> Path:
    """Ensure directory exists and return resolved Path object."""
    p = normalize_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_join(base_dir: Union[str, Path], *paths: str) -> Path:
    """Safely join paths preventing directory traversal attacks."""
    base = normalize_path(base_dir)
    target = normalize_path(base.joinpath(*paths))
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError(f"Directory traversal detected: {target} is outside {base}")
    return target


def atomic_write_bytes(
    file_path: Union[str, Path],
    data: bytes,
    max_retries: int = 5,
    retry_delay: float = 0.05
) -> Path:
    """Atomically write binary data to file with fsync and safe tempfile replacement."""
    target = normalize_path(file_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".tmp_{target.name}_",
        suffix=".tmp"
    )

    try:
        with os.fdopen(temp_fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        for attempt in range(max_retries):
            try:
                os.replace(temp_path, target)
                break
            except (PermissionError, OSError) as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay * (2 ** attempt))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    return target


def atomic_write_text(
    file_path: Union[str, Path],
    text: str,
    encoding: str = "utf-8",
    max_retries: int = 5
) -> Path:
    """Atomically write text content with standard UTF-8 encoding."""
    return atomic_write_bytes(file_path, text.encode(encoding), max_retries=max_retries)


def safe_read_bytes(file_path: Union[str, Path]) -> bytes:
    """Read binary data safely."""
    with open(normalize_path(file_path), "rb") as f:
        return f.read()


def safe_read_text(
    file_path: Union[str, Path],
    fallback_encodings: Optional[List[str]] = None
) -> str:
    """Read text with UTF-8 first and fallbacks for Windows-1252/Latin-1."""
    if fallback_encodings is None:
        fallback_encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    raw = safe_read_bytes(file_path)
    for enc in fallback_encodings:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def get_default_storage_dir() -> Path:
    """Determine OS-specific default storage directory for glitch artifacts."""
    if IS_TERMUX:
        base = Path(os.environ.get("HOME", "/data/data/com.termux/files/home")) / ".datamosh"
    elif IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DatamoshStudio"
    elif IS_MACOS:
        base = Path.home() / "Library" / "Application Support" / "DatamoshStudio"
    else:
        base = Path.home() / ".local" / "share" / "datamosh_studio"

    base.mkdir(parents=True, exist_ok=True)
    return base
