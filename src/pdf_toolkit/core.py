import errno
import os
from pathlib import Path
from tempfile import TemporaryDirectory
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
        将单页或多页 PDF 拆分为单页文件，不覆盖已有目标。

        :param input_path: 输入 PDF 文件路径
        :param output_dir: 输出文件夹路径
        :return: 生成的 PDF 文件路径列表
        :raises FileExistsError: 任一目标已存在（包括符号链接或目录）

        先检查所有目标，再暂存全部页面。发布时使用不覆盖目标的硬链接；
        如发布中途发生竞争或 I/O 错误，已发布的完整页面会保留。
        输出文件系统必须支持硬链接，不支持时会安全失败。
        """
        reader = PdfReader(str(input_path))
        output_directory = Path(output_dir)
        input_filename = Path(input_path).stem
        generated_files = [
            output_directory / f"{input_filename}_page_{idx}.pdf"
            for idx in range(1, len(reader.pages) + 1)
        ]

        # lstat also detects dangling symlinks, unlike exists(). Check every
        # destination before publishing anything, even a collision on a later page.
        for output_file in generated_files:
            try:
                output_file.lstat()
            except FileNotFoundError:
                continue
            raise FileExistsError(
                errno.EEXIST, "Refusing to overwrite existing output", str(output_file)
            )

        output_directory.mkdir(parents=True, exist_ok=True)
        # Stage on the destination filesystem so link() can publish complete
        # files atomically. Never fall back to a replacing rename or a wb open:
        # another process can create a destination after the preflight check.
        with TemporaryDirectory(prefix=".pdf-toolkit-", dir=output_directory) as staging:
            staged_files = []
            for idx, page in enumerate(reader.pages, start=1):
                writer = PdfWriter()
                writer.add_page(page)
                staged_file = Path(staging) / f"{idx}.pdf"
                with staged_file.open("wb") as stream:
                    writer.write(stream)
                staged_files.append(staged_file)

            for staged_file, output_file in zip(staged_files, generated_files):
                os.link(staged_file, output_file)

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
