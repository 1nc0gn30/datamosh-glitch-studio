"""Tests for cross-platform compatibility utilities."""

import os
import sys
import tempfile
from pathlib import Path
import pytest

from datamosh_glitch_studio.compat import (
    normalize_path,
    ensure_dir,
    safe_join,
    atomic_write_bytes,
    atomic_write_text,
    safe_read_bytes,
    safe_read_text,
    get_default_storage_dir,
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS
)


def test_normalize_path():
    p = normalize_path(".")
    assert p.is_absolute()


def test_ensure_dir(tmp_path):
    sub = tmp_path / "sub" / "folder"
    res = ensure_dir(sub)
    assert res.is_dir()


def test_safe_join(tmp_path):
    valid = safe_join(tmp_path, "test.txt")
    assert valid.name == "test.txt"

    with pytest.raises(PermissionError):
        safe_join(tmp_path, "../outside.txt")


def test_atomic_write_and_safe_read(tmp_path):
    target = tmp_path / "file.dat"
    content = b"\x00\x01\x02\xFF"
    atomic_write_bytes(target, content)
    assert target.exists()
    assert safe_read_bytes(target) == content

    txt_target = tmp_path / "file.txt"
    atomic_write_text(txt_target, "Hello Glitch 📼")
    assert "Hello Glitch 📼" in safe_read_text(txt_target)


def test_get_default_storage_dir():
    dir_path = get_default_storage_dir()
    assert dir_path.is_dir()
