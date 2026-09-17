"""Tests for Command-Line Interface."""

import pytest
from datamosh_glitch_studio.cli import main


def test_cli_help(capsys):
    ret = main([])
    assert ret == 0
    out = capsys.readouterr().out
    assert "datamosh-studio" in out

    with pytest.raises(SystemExit):
        main(["--help"])


def test_cli_presets(capsys):
    ret = main(["presets"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "H.264 I-Frame Drop" in out


def test_cli_presets_json(capsys):
    ret = main(["presets", "--json"])
    assert ret == 0
    out = capsys.readouterr().out
    assert '"id": "h264_iframe_drop"' in out


def test_cli_mosh_testcard(tmp_path, capsys):
    out_file = tmp_path / "glitch.bmp"
    ret = main(["mosh", "-p", "cyberpunk_vcr", "-o", str(out_file), "--width", "64", "--height", "48", "--seed", "42"])
    assert ret == 0
    assert out_file.exists()
    out = capsys.readouterr().out
    assert "Glitched frame generated successfully" in out


def test_cli_corrupt(tmp_path, capsys):
    in_file = tmp_path / "data.bin"
    out_file = tmp_path / "corrupt.bin"
    in_file.write_bytes(b"A" * 500)

    ret = main(["corrupt", str(in_file), "-o", str(out_file), "--rate", "0.05", "--header-skip", "10"])
    assert ret == 0
    assert out_file.exists()


def test_cli_doctor(capsys):
    ret = main(["doctor"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "HEALTHY" in out


def test_cli_test_command(capsys):
    ret = main(["test"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "All internal checks passed" in out
