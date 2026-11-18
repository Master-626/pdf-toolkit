import pytest
from PyPDF2 import PdfWriter
from PyPDF2.generic import DecodedStreamObject, DictionaryObject, NameObject

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
    assert out_txt.read_text(encoding="utf-8") == text


def test_extract_text_reads_real_page_content(tmp_path):
    pdf_path = tmp_path / "words.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    page = writer.pages[-1]
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 18 Tf 40 100 Td (Hello) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    fonts = DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
    with pdf_path.open("wb") as stream_out:
        writer.write(stream_out)

    assert PDFToolkit.extract_text(pdf_path) == "--- Page 1 ---\nHello"
