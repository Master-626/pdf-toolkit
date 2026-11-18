"""Merge must combine the files the caller named, and no others."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PyPDF2 import PdfReader, PdfWriter

from pdf_toolkit import core
from pdf_toolkit.core import PDFToolkit


def write_pdf(path, widths):
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=width)
    with path.open("wb") as stream:
        writer.write(stream)


def widths(path):
    return [float(page.mediabox.width) for page in PdfReader(path).pages]


def run_cli(arguments):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(core.__file__).parents[1])
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "pdf_toolkit.cli", *arguments],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_string_input_is_not_split_into_character_paths(tmp_path, monkeypatch):
    """A path string must not silently merge one-character filenames."""
    monkeypatch.chdir(tmp_path)
    write_pdf(Path("a"), [11])
    write_pdf(Path("b"), [22])
    write_pdf(Path("ab"), [33])
    before = {name: Path(name).read_bytes() for name in ("a", "b", "ab")}

    with pytest.raises(TypeError, match="iterable of PDF paths"):
        PDFToolkit.merge_pdfs("ab", "out.pdf")

    assert not Path("out.pdf").exists()
    assert {name: Path(name).read_bytes() for name in ("a", "b", "ab")} == before
    with pytest.raises(TypeError, match="iterable of PDF paths"):
        PDFToolkit.merge_pdfs(b"ab", "out2.pdf")
    with pytest.raises(TypeError, match="iterable of PDF paths"):
        PDFToolkit.merge_pdfs(Path("ab"), "out3.pdf")
    assert not Path("out2.pdf").exists()
    assert not Path("out3.pdf").exists()


def test_empty_merge_creates_nothing(tmp_path):
    output = tmp_path / "nested" / "out.pdf"
    with pytest.raises(ValueError, match="at least one PDF file"):
        PDFToolkit.merge_pdfs([], output)
    assert not (tmp_path / "nested").exists()


def test_empty_merge_still_refuses_existing_output(tmp_path):
    output = tmp_path / "out.pdf"
    output.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        PDFToolkit.merge_pdfs([], output)
    assert output.read_bytes() == b"keep"


def test_tuples_and_generators_merge_in_order(tmp_path):
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    write_pdf(first, [100])
    write_pdf(second, [200])

    tuple_out = tmp_path / "tuple.pdf"
    PDFToolkit.merge_pdfs((first, second), tuple_out)
    assert widths(tuple_out) == [100, 200]

    def generate():
        yield first
        yield second

    generator_out = tmp_path / "generator.pdf"
    PDFToolkit.merge_pdfs(generate(), generator_out)
    assert widths(generator_out) == [100, 200]


def test_repeated_input_flags_merge_every_file(tmp_path):
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    output = tmp_path / "merged.pdf"
    write_pdf(first, [100])
    write_pdf(second, [200])

    result = run_cli(
        ["merge", "-i", str(first), "-i", str(second), "-o", str(output)]
    )

    assert result.returncode == 0, result.stderr
    assert widths(output) == [100, 200]


def test_one_input_flag_still_accepts_several_paths(tmp_path):
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    output = tmp_path / "merged.pdf"
    write_pdf(first, [100, 110])
    write_pdf(second, [200])

    result = run_cli(["merge", "-i", str(first), str(second), "-o", str(output)])

    assert result.returncode == 0, result.stderr
    assert widths(output) == [100, 110, 200]
