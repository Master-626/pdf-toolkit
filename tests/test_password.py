"""Encrypted PDFs open only with the supplied password."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import FileNotDecryptedError, WrongPasswordError
from PyPDF2.generic import DecodedStreamObject, DictionaryObject, NameObject

from pdf_toolkit import core
from pdf_toolkit.core import PDFToolkit

PASSWORD = "secret"


def write_pdf(path, widths, password=None):
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=width)
    if password is not None:
        writer.encrypt(password)
    with path.open("wb") as stream:
        writer.write(stream)


def write_text_pdf(path, pages, password=None):
    writer = PdfWriter()
    for text in pages:
        writer.add_blank_page(width=300, height=200)
        page = writer.pages[-1]
        stream = DecodedStreamObject()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(f"BT /F1 18 Tf 40 100 Td ({escaped}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        font = DictionaryObject()
        font[NameObject("/Type")] = NameObject("/Font")
        font[NameObject("/Subtype")] = NameObject("/Type1")
        font[NameObject("/BaseFont")] = NameObject("/Helvetica")
        fonts = DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
    if password is not None:
        writer.encrypt(password)
    with path.open("wb") as stream:
        writer.write(stream)


def widths(path):
    reader = PdfReader(path)
    return [float(page.mediabox.width) for page in reader.pages]


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


@pytest.fixture
def encrypted(tmp_path):
    path = tmp_path / "encrypted.pdf"
    write_pdf(path, [100, 200], password=PASSWORD)
    return path


def test_encrypted_pdf_requires_password(tmp_path, encrypted):
    output = tmp_path / "merged.pdf"
    with pytest.raises(FileNotDecryptedError):
        PDFToolkit.merge_pdfs([encrypted], output)
    assert not output.exists()

    with pytest.raises(FileNotDecryptedError):
        PDFToolkit.split_pdf(encrypted, tmp_path / "pages")
    assert not (tmp_path / "pages").exists()

    with pytest.raises(FileNotDecryptedError):
        PDFToolkit.extract_text(encrypted, tmp_path / "text.txt")
    assert not (tmp_path / "text.txt").exists()


def test_wrong_password_creates_nothing(tmp_path, encrypted):
    with pytest.raises(WrongPasswordError, match="Wrong password"):
        PDFToolkit.merge_pdfs([encrypted], tmp_path / "merged.pdf", password="nope")
    with pytest.raises(WrongPasswordError, match="Wrong password"):
        PDFToolkit.split_pdf(encrypted, tmp_path / "pages", password="nope")
    with pytest.raises(WrongPasswordError, match="Wrong password"):
        PDFToolkit.extract_text(encrypted, tmp_path / "text.txt", password="nope")
    assert list(tmp_path.iterdir()) == [encrypted]


def test_password_merges_splits_and_extracts(tmp_path, encrypted):
    merged = tmp_path / "merged.pdf"
    PDFToolkit.merge_pdfs([encrypted, encrypted], merged, password=PASSWORD)
    assert widths(merged) == [100, 200, 100, 200]
    assert not PdfReader(merged).is_encrypted

    pages = PDFToolkit.split_pdf(encrypted, tmp_path / "pages", password=PASSWORD)
    assert [widths(page) for page in pages] == [[100], [200]]

    text_path = tmp_path / "text.txt"
    source = tmp_path / "words.pdf"
    write_text_pdf(source, ["Alpha", "Beta"], password=PASSWORD)
    text = PDFToolkit.extract_text(source, text_path, password=PASSWORD)
    assert text == "--- Page 1 ---\nAlpha\n\n--- Page 2 ---\nBeta"
    assert text_path.read_text(encoding="utf-8") == text

    merged_text = tmp_path / "merged-text.pdf"
    PDFToolkit.merge_pdfs([source, source], merged_text, password=PASSWORD)
    assert PDFToolkit.extract_text(merged_text) == (
        "--- Page 1 ---\nAlpha\n\n--- Page 2 ---\nBeta\n\n"
        "--- Page 3 ---\nAlpha\n\n--- Page 4 ---\nBeta"
    )
    word_pages = PDFToolkit.split_pdf(source, tmp_path / "words", password=PASSWORD)
    assert PDFToolkit.extract_text(word_pages[0]) == "--- Page 1 ---\nAlpha"
    assert PDFToolkit.extract_text(word_pages[1]) == "--- Page 1 ---\nBeta"


def test_password_is_ignored_for_unencrypted_files(tmp_path, encrypted):
    plain = tmp_path / "plain.pdf"
    write_pdf(plain, [50])
    merged = tmp_path / "merged.pdf"
    PDFToolkit.merge_pdfs([plain, encrypted], merged, password=PASSWORD)
    assert widths(merged) == [50, 100, 200]

    text = PDFToolkit.extract_text(plain, password=PASSWORD)
    assert text.startswith("--- Page 1 ---")
    assert len(PDFToolkit.split_pdf(plain, tmp_path / "plain-pages", password=PASSWORD)) == 1


def test_correct_password_still_refuses_existing_output(tmp_path, encrypted):
    output = tmp_path / "merged.pdf"
    output.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        PDFToolkit.merge_pdfs([encrypted], output, password=PASSWORD)
    assert output.read_bytes() == b"keep"


def test_cli_password_opens_encrypted_pdf_without_echoing_it(tmp_path, encrypted):
    merged = tmp_path / "merged.pdf"
    missing = run_cli(["merge", "-i", str(encrypted), "-o", str(merged)])
    assert missing.returncode == 1
    assert not merged.exists()

    wrong = run_cli(
        ["merge", "-i", str(encrypted), "-o", str(merged), "-p", "not-the-secret"]
    )
    assert wrong.returncode == 1
    assert "Wrong password" in wrong.stderr
    assert "not-the-secret" not in wrong.stderr
    assert not merged.exists()

    opened = run_cli(
        ["merge", "-i", str(encrypted), "-o", str(merged), "-p", PASSWORD]
    )
    assert opened.returncode == 0, opened.stderr
    assert widths(merged) == [100, 200]

    extracted = run_cli(["extract", "-i", str(encrypted), "-p", PASSWORD])
    assert extracted.returncode == 0, extracted.stderr
    assert "--- Page 1 ---" in extracted.stdout
    assert PASSWORD not in extracted.stdout

    split_dir = tmp_path / "pages"
    refused = run_cli(
        ["split", "-i", str(encrypted), "-o", str(split_dir), "-p", "nope"]
    )
    assert refused.returncode == 1
    assert not split_dir.exists()


def test_help_lists_password_option():
    result = run_cli(["merge", "--help"])
    assert result.returncode == 0
    assert "--password" in result.stdout
    assert "可重复使用 -i" in result.stdout
