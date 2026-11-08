"""Regression tests use generated PDFs and temporary directories only."""

import errno
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import FileNotDecryptedError, PdfReadError

from pdf_toolkit import core
from pdf_toolkit.core import PDFToolkit


def write_pdf(path, widths):
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=width)
    with path.open("wb") as stream:
        writer.write(stream)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.pdf"
    write_pdf(path, [100, 200, 300])
    return path


def assert_no_staging(directory):
    assert not list(directory.glob(".pdf-toolkit-*"))


def make_symlink(link, target):
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Symlinks are not available: {error}")


def test_split_publishes_ordered_complete_pages(tmp_path, source):
    output = tmp_path / "nested" / "split"
    before = source.read_bytes()
    files = PDFToolkit.split_pdf(str(source), str(output))
    assert files == [output / f"source_page_{i}.pdf" for i in (1, 2, 3)]
    for file, width in zip(files, (100, 200, 300)):
        reader = PdfReader(file)
        assert len(reader.pages) == 1
        assert float(reader.pages[0].mediabox.width) == width
    assert source.read_bytes() == before
    assert_no_staging(output)


@pytest.mark.parametrize("page", [1, 2, 3])
def test_any_existing_pdf_prevents_all_output(tmp_path, source, page):
    output = tmp_path / "split"
    output.mkdir()
    victim = output / f"source_page_{page}.pdf"
    write_pdf(victim, [700])
    before = victim.read_bytes()
    with pytest.raises(FileExistsError) as error:
        PDFToolkit.split_pdf(source, output)
    assert error.value.filename == str(victim)
    assert victim.read_bytes() == before
    assert list(output.iterdir()) == [victim]


def test_repeated_split_preserves_every_output(tmp_path, source):
    output = tmp_path / "split"
    files = PDFToolkit.split_pdf(source, output)
    before = {file: file.read_bytes() for file in files}
    with pytest.raises(FileExistsError):
        PDFToolkit.split_pdf(source, output)
    assert {file: file.read_bytes() for file in files} == before
    assert_no_staging(output)


def test_existing_directory_is_a_conflict(tmp_path, source):
    output = tmp_path / "split"
    victim = output / "source_page_3.pdf"
    victim.mkdir(parents=True)
    (victim / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        PDFToolkit.split_pdf(source, output)
    assert list(output.iterdir()) == [victim]
    assert (victim / "keep.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("dangling", [False, True])
def test_existing_symlink_is_a_conflict(tmp_path, source, dangling):
    output = tmp_path / "split"
    output.mkdir()
    external = tmp_path / "external.pdf"
    if not dangling:
        write_pdf(external, [700])
    before = external.read_bytes() if not dangling else None
    link = output / "source_page_3.pdf"
    make_symlink(link, external)
    with pytest.raises(FileExistsError):
        PDFToolkit.split_pdf(source, output)
    assert link.is_symlink()
    assert list(output.iterdir()) == [link]
    assert (external.read_bytes() if external.exists() else None) == before


def test_hardlink_to_source_is_a_conflict(tmp_path, source):
    output = tmp_path / "split"
    output.mkdir()
    victim = output / "source_page_2.pdf"
    os.link(source, victim)
    before = source.read_bytes()
    with pytest.raises(FileExistsError):
        PDFToolkit.split_pdf(source, output)
    assert source.read_bytes() == before
    assert victim.read_bytes() == before
    assert list(output.iterdir()) == [victim]


def test_unrelated_output_is_untouched(tmp_path, source):
    output = tmp_path / "split"
    output.mkdir()
    unrelated = output / "keep.pdf"
    write_pdf(unrelated, [700])
    before = unrelated.read_bytes()
    assert len(PDFToolkit.split_pdf(source, output)) == 3
    assert unrelated.read_bytes() == before
    assert_no_staging(output)


@pytest.mark.parametrize("failed_page", [1, 3])
def test_serialization_failure_leaves_no_published_pages(
    tmp_path, source, monkeypatch, failed_page
):
    original = PdfWriter.write
    calls = 0

    def fail_partway(writer, stream):
        nonlocal calls
        calls += 1
        if calls == failed_page:
            stream.write(b"partial invalid PDF")
            raise OSError("simulated disk failure")
        return original(writer, stream)

    monkeypatch.setattr(PdfWriter, "write", fail_partway)
    output = tmp_path / "split"
    before = source.read_bytes()
    with pytest.raises(OSError, match="simulated disk failure"):
        PDFToolkit.split_pdf(source, output)
    assert list(output.iterdir()) == []
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "target_kind", ["file", "symlink", "dangling_symlink", "directory"]
)
def test_new_destination_after_preflight_is_never_replaced(
    tmp_path, source, monkeypatch, target_kind
):
    output = tmp_path / "split"
    victim = output / "source_page_2.pdf"
    external = tmp_path / "external.pdf"
    write_pdf(external, [700])
    before = external.read_bytes()
    real_link = os.link

    def competing_link(staged, destination):
        if destination == victim:
            if target_kind == "file":
                victim.write_bytes(before)
            elif target_kind == "directory":
                victim.mkdir()
            else:
                make_symlink(
                    victim,
                    external if target_kind == "symlink" else tmp_path / "absent.pdf",
                )
        return real_link(staged, destination)

    monkeypatch.setattr(core.os, "link", competing_link)
    with pytest.raises(FileExistsError):
        PDFToolkit.split_pdf(source, output)
    if target_kind == "file":
        assert victim.read_bytes() == before
    elif target_kind == "directory":
        assert victim.is_dir()
    else:
        assert victim.is_symlink()
    assert external.read_bytes() == before
    first = output / "source_page_1.pdf"
    assert float(PdfReader(first).pages[0].mediabox.width) == 100
    assert not (output / "source_page_3.pdf").exists()
    assert_no_staging(output)


def test_unsupported_links_fail_without_publishing(tmp_path, source, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError(errno.ENOTSUP, "simulated unsupported filesystem")

    monkeypatch.setattr(core.os, "link", unavailable)
    output = tmp_path / "split"
    with pytest.raises(OSError, match="unsupported filesystem"):
        PDFToolkit.split_pdf(source, output)
    assert list(output.iterdir()) == []


@pytest.mark.parametrize(
    "kind, error",
    [
        ("missing", FileNotFoundError),
        ("corrupt", PdfReadError),
        ("encrypted", FileNotDecryptedError),
    ],
)
def test_invalid_input_does_not_create_output(tmp_path, kind, error):
    source = tmp_path / "input.pdf"
    if kind == "corrupt":
        source.write_bytes(b"not a PDF")
    elif kind == "encrypted":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("temporary-test-password")
        with source.open("wb") as stream:
            writer.write(stream)
    output = tmp_path / "split"
    with pytest.raises(error):
        PDFToolkit.split_pdf(source, output)
    assert not output.exists()


def test_cli_conflict_fails_without_success_or_data_loss(tmp_path, source):
    output = tmp_path / "split"
    output.mkdir()
    victim = output / "source_page_3.pdf"
    write_pdf(victim, [700])
    before = victim.read_bytes()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(core.__file__).parents[1])
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf_toolkit.cli",
            "split",
            "-i",
            str(source),
            "-o",
            str(output),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 1
    assert not result.stdout
    # OSError renders Windows paths with escaped backslashes.
    assert victim.name in result.stderr
    assert "Refusing to overwrite existing output" in result.stderr
    assert victim.read_bytes() == before
    assert list(output.iterdir()) == [victim]
