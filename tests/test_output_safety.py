"""Protect existing data and publish only complete merge/extract outputs."""

import errno
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PyPDF2._page import PageObject
from PyPDF2.errors import PdfReadError

from pdf_toolkit import core
from pdf_toolkit.core import PDFToolkit


@pytest.fixture
def source(tmp_path):
    source = tmp_path / "源文件.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=200, height=200)
    with source.open("wb") as stream:
        writer.write(stream)
    return source


def run_operation(operation, source, output):
    if operation == "merge":
        return PDFToolkit.merge_pdfs([source, source], output)
    return PDFToolkit.extract_text(source, output)


def snapshot(root):
    """Include link identity rather than following links to their targets."""
    entries = {}
    for path in root.rglob("*"):
        key = str(path.relative_to(root))
        if path.is_symlink():
            entries[key] = ("symlink", os.readlink(path))
        elif path.is_dir():
            entries[key] = ("directory", None)
        else:
            entries[key] = ("file", path.read_bytes())
    return entries


def make_symlink(link, target):
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Symlinks are not available: {error}")


def assert_no_staging(root):
    assert not list(root.rglob(".pdf-toolkit-*"))


@pytest.mark.parametrize("operation", ["merge", "extract"])
@pytest.mark.parametrize(
    "kind", ["file", "directory", "symlink", "dangling", "hardlink", "input"]
)
def test_existing_output_entries_are_preserved(tmp_path, source, operation, kind):
    output = tmp_path / "output"
    if kind == "file":
        output.write_bytes(b"valuable existing data")
    elif kind == "directory":
        output.mkdir()
        (output / "keep.txt").write_bytes(b"valuable nested data")
    elif kind == "symlink":
        make_symlink(output, source)
    elif kind == "dangling":
        make_symlink(output, tmp_path / "absent.pdf")
    elif kind == "hardlink":
        os.link(source, output)
    elif kind == "input":
        output = source
    before = snapshot(tmp_path)
    with pytest.raises(FileExistsError) as error:
        run_operation(operation, source, output)
    assert error.value.filename == str(output)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("operation", ["merge", "extract"])
def test_success_and_repeat_preserve_sources(tmp_path, source, operation):
    output = tmp_path / "nested" / "output"
    before = source.read_bytes()
    result = run_operation(operation, str(source), str(output))
    assert source.read_bytes() == before
    if operation == "merge":
        assert result is None
        reader = PdfReader(output)
        assert [float(page.mediabox.width) for page in reader.pages] == [
            100,
            200,
            100,
            200,
        ]
    else:
        assert output.read_text(encoding="utf-8") == result
        assert "--- Page 1 ---" in result
        assert "--- Page 2 ---" in result
    snapshot_before_repeat = snapshot(tmp_path)
    with pytest.raises(FileExistsError):
        run_operation(operation, source, output)
    assert snapshot(tmp_path) == snapshot_before_repeat
    assert_no_staging(tmp_path)


def test_extract_writes_utf8_and_retains_return_value(tmp_path, source, monkeypatch):
    monkeypatch.setattr(PageObject, "extract_text", lambda page: "中文 • café 🌍")
    output = tmp_path / "text.txt"
    result = PDFToolkit.extract_text(source, output)
    assert result == "--- Page 1 ---\n中文 • café 🌍\n\n--- Page 2 ---\n中文 • café 🌍"
    assert output.read_text(encoding="utf-8") == result
    assert_no_staging(tmp_path)


def test_extract_without_output_creates_nothing(tmp_path, source):
    before = snapshot(tmp_path)
    text = PDFToolkit.extract_text(source)
    assert "--- Page 1 ---" in text
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("operation", ["merge", "extract"])
@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "dangling"])
def test_output_created_after_preflight_wins(
    tmp_path, source, monkeypatch, operation, kind
):
    output = tmp_path / "output"
    before_source = source.read_bytes()
    original_link = os.link
    winning_snapshot = None

    def racing_link(staged, destination):
        nonlocal winning_snapshot
        assert destination == output
        if kind == "file":
            output.write_bytes(b"created by another writer")
        elif kind == "directory":
            output.mkdir()
            (output / "keep.txt").write_bytes(b"keep")
        elif kind == "symlink":
            make_symlink(output, source)
        else:
            make_symlink(output, tmp_path / "absent.txt")
        winning_snapshot = {
            path: data
            for path, data in snapshot(tmp_path).items()
            if not path.startswith(".pdf-toolkit-")
        }
        return original_link(staged, destination)

    monkeypatch.setattr(core.os, "link", racing_link)
    with pytest.raises(FileExistsError):
        run_operation(operation, source, output)
    assert source.read_bytes() == before_source
    assert snapshot(tmp_path) == winning_snapshot
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("operation", ["merge", "extract"])
@pytest.mark.parametrize("error_number", [errno.EACCES, errno.ENOSPC, errno.ENOTSUP])
def test_publication_failure_never_falls_back_to_direct_write(
    tmp_path, source, monkeypatch, operation, error_number
):
    output = tmp_path / "output"
    before = snapshot(tmp_path)

    def fail_publication(*args, **kwargs):
        raise OSError(error_number, "simulated publication failure")

    monkeypatch.setattr(core.os, "link", fail_publication)
    with pytest.raises(OSError, match="simulated publication failure"):
        run_operation(operation, source, output)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("operation", ["merge", "extract"])
def test_serialization_failure_leaves_no_partial_target(
    tmp_path, source, monkeypatch, operation
):
    output = tmp_path / "output"
    before = snapshot(tmp_path)
    if operation == "merge":

        def fail_write(merger, stream):
            stream.write(b"partial broken PDF")
            raise OSError("simulated write failure")

        monkeypatch.setattr(PdfMerger, "write", fail_write)
    else:

        def fail_text_write(path, text, **kwargs):
            path.write_bytes(b"partial extracted text")
            raise OSError("simulated write failure")

        monkeypatch.setattr(Path, "write_text", fail_text_write)
    with pytest.raises(OSError, match="simulated write failure"):
        run_operation(operation, source, output)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("failure_stage", ["append", "write", "publish"])
def test_merge_releases_resources_on_failure(
    tmp_path, source, monkeypatch, failure_stage
):
    real_merger = PdfMerger
    instances = []

    class TrackingMerger(real_merger):
        closed = False

        def __init__(self):
            super().__init__()
            instances.append(self)

        def append(self, path):
            super().append(path)
            if failure_stage == "append":
                raise OSError("simulated merge failure")

        def write(self, stream):
            if failure_stage == "write":
                stream.write(b"partial PDF")
                raise OSError("simulated merge failure")
            return super().write(stream)

        def close(self):
            super().close()
            self.closed = True

    monkeypatch.setattr(core, "PdfMerger", TrackingMerger)
    if failure_stage == "publish":

        def fail_link(*args, **kwargs):
            raise OSError("simulated merge failure")

        monkeypatch.setattr(core.os, "link", fail_link)
    output = tmp_path / "output"
    with pytest.raises(OSError, match="simulated merge failure"):
        run_operation("merge", source, output)
    assert len(instances) == 1
    assert instances[0].closed
    assert instances[0].inputs == []
    assert instances[0].output is None
    assert not output.exists()
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("operation", ["merge", "extract"])
@pytest.mark.parametrize(
    "kind,error", [("missing", FileNotFoundError), ("corrupt", PdfReadError)]
)
def test_invalid_source_does_not_create_output(tmp_path, operation, kind, error):
    source = tmp_path / "invalid.pdf"
    if kind == "corrupt":
        source.write_bytes(b"not a PDF")
    output = tmp_path / "new-directory" / "output"
    before = snapshot(tmp_path)
    with pytest.raises(error):
        run_operation(operation, source, output)
    assert snapshot(tmp_path) == before


def test_extract_page_failure_creates_nothing(tmp_path, source, monkeypatch):
    calls = 0

    def extract_page(page):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("simulated invalid text content")
        return "first page"

    monkeypatch.setattr(PageObject, "extract_text", extract_page)
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="invalid text content"):
        PDFToolkit.extract_text(source, tmp_path / "output")
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("operation", ["merge", "extract"])
def test_simultaneous_writers_publish_exactly_one_complete_file(
    tmp_path, source, monkeypatch, operation
):
    output = tmp_path / "output"
    barrier = threading.Barrier(2)
    original_link = os.link

    def synchronized_link(staged, destination):
        barrier.wait(timeout=20)
        return original_link(staged, destination)

    monkeypatch.setattr(core.os, "link", synchronized_link)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(run_operation, operation, source, output) for _ in range(2)
        ]
        errors = [future.exception() for future in futures]
    assert sum(error is None for error in errors) == 1
    assert sum(isinstance(error, FileExistsError) for error in errors) == 1
    if operation == "merge":
        assert len(PdfReader(output).pages) == 4
    else:
        assert output.read_text(encoding="utf-8") == PDFToolkit.extract_text(source)
    assert_no_staging(tmp_path)


@pytest.mark.parametrize("operation", ["merge", "extract"])
def test_cli_conflict_reports_failure_without_modifying_target(
    tmp_path, source, operation
):
    target = tmp_path / "existing"
    target.write_bytes(b"valuable contents")
    before = snapshot(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(core.__file__).parents[1])
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf_toolkit.cli",
            operation,
            "-i",
            str(source),
            "-o",
            str(target),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 1
    assert not result.stdout
    assert "Refusing to overwrite existing output" in result.stderr
    assert snapshot(tmp_path) == before
