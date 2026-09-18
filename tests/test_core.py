import pytest
from pathlib import Path
from PyPDF2 import PdfWriter
from pdf_toolkit.core import PDFToolkit


@pytest.fixture
def sample_pdf(tmp_path):
    """生成包含 2 页的临时测试 PDF"""
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


def test_merge_pdfs(tmp_path, sample_pdf):
    out_pdf = tmp_path / "merged.pdf"
    PDFToolkit.merge_pdfs([sample_pdf, sample_pdf], out_pdf)
    assert out_pdf.exists()


def test_split_pdf(tmp_path, sample_pdf):
    output_dir = tmp_path / "split_output"
    files = PDFToolkit.split_pdf(sample_pdf, output_dir)
    assert len(files) == 2
    assert all(f.exists() for f in files)


def test_extract_text(tmp_path, sample_pdf):
    out_txt = tmp_path / "extracted.txt"
    text = PDFToolkit.extract_text(sample_pdf, out_txt)
    assert out_txt.exists()
    assert "--- Page 1 ---" in text
