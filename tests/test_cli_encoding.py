"""Legacy console encodings must not turn completed operations into failures."""

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PyPDF2 import PdfReader, PdfWriter

from pdf_toolkit import cli


def invoke(arguments, encoding):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(cli.__file__).parents[1])
    env["PYTHONIOENCODING"] = encoding + ":strict"
    return subprocess.run(
        [sys.executable, "-m", "pdf_toolkit.cli"] + arguments,
        env=env,
        capture_output=True,
        text=True,
        encoding=encoding,
        check=False,
    )


@pytest.mark.parametrize("encoding", ["cp1252", "ascii", "utf-8"])
def test_help_and_parser_errors_work_with_legacy_encoding(encoding):
    result = invoke(["--help"], encoding)
    assert result.returncode == 0
    assert "PDF Toolkit" in result.stdout
    assert not result.stderr

    result = invoke(["split"], encoding)
    assert result.returncode == 2
    assert "--input" in result.stderr
    assert "UnicodeEncodeError" not in result.stderr


@pytest.mark.parametrize("encoding", ["cp1252", "ascii", "utf-8"])
def test_split_and_conflict_keep_correct_exit_status(tmp_path, encoding):
    source = tmp_path / "文档.pdf"
    output = tmp_path / "拆分"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with source.open("wb") as stream:
        writer.write(stream)
    arguments = ["split", "-i", str(source), "-o", str(output)]

    first = invoke(arguments, encoding)
    assert first.returncode == 0, first.stderr
    assert first.stdout
    victim = output / "文档_page_1.pdf"
    before = victim.read_bytes()
    assert len(PdfReader(victim).pages) == 1

    second = invoke(arguments, encoding)
    assert second.returncode == 1
    assert not second.stdout
    assert "Refusing to overwrite existing output" in second.stderr
    assert "UnicodeEncodeError" not in second.stderr
    assert victim.read_bytes() == before


def test_embedded_main_restores_caller_stream_settings(monkeypatch):
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "argv", ["pdf-toolkit", "--help"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 0
    assert stdout.encoding == stderr.encoding == "cp1252"
    assert stdout.errors == stderr.errors == "strict"


def test_main_supports_streams_without_reconfigure(monkeypatch):
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "argv", ["pdf-toolkit", "--help"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 0
    assert "PDF Toolkit" in stdout.getvalue()
