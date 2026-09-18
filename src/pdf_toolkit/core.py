from pathlib import Path
from typing import List, Union
from PyPDF2 import PdfMerger, PdfReader, PdfWriter


class PDFToolkit:
    """PDF核心功能处理类"""

    @staticmethod
    def merge_pdfs(input_paths: List[Union[str, Path]], output_path: Union[str, Path]) -> None:
        """
        合并多个 PDF 文件为一个文件。

        :param input_paths: 输入 PDF 文件路径列表
        :param output_path: 输出 PDF 文件路径
        """
        merger = PdfMerger()
        for path in input_paths:
            merger.append(str(path))
        
        output_p = Path(output_path)
        output_p.parent.mkdir(parents=True, exist_ok=True)
        merger.write(str(output_p))
        merger.close()

    @staticmethod
    def split_pdf(input_path: Union[str, Path], output_dir: Union[str, Path]) -> List[Path]:
        """
        将单页或多页 PDF 拆分为单页文件。

        :param input_path: 输入 PDF 文件路径
        :param output_dir: 输出文件夹路径
        :return: 生成的 PDF 文件路径列表
        """
        reader = PdfReader(str(input_path))
        output_directory = Path(output_dir)
        output_directory.mkdir(parents=True, exist_ok=True)
        
        generated_files = []
        input_filename = Path(input_path).stem

        for idx, page in enumerate(reader.pages, start=1):
            writer = PdfWriter()
            writer.add_page(page)
            
            output_file = output_directory / f"{input_filename}_page_{idx}.pdf"
            with open(output_file, "wb") as f:
                writer.write(f)
            generated_files.append(output_file)

        return generated_files

    @staticmethod
    def extract_text(input_path: Union[str, Path], output_txt: Union[str, Path] = None) -> str:
        """
        提取 PDF 中的文本内容。

        :param input_path: 输入 PDF 文件路径
        :param output_txt: 可选，将文本写入的 txt 文件路径
        :return: 提取的全部文本
        """
        reader = PdfReader(str(input_path))
        full_text = []

        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            full_text.append(f"--- Page {idx} ---\n{text}")

        extracted_string = "\n\n".join(full_text)

        if output_txt:
            out_p = Path(output_txt)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(extracted_string, encoding="utf-8")

        return extracted_string
