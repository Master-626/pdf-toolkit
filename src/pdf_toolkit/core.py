import errno
import os
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, List, Optional, Union

from PyPDF2 import PasswordType, PdfMerger, PdfReader, PdfWriter
from PyPDF2.errors import WrongPasswordError


def _open_reader(
    path: Union[str, Path], password: Optional[str] = None
) -> PdfReader:
    """Open a PDF, decrypting it only when a password is supplied."""
    reader = PdfReader(str(path))
    if password is None or not reader.is_encrypted:
        return reader
    if reader.decrypt(password) == PasswordType.NOT_DECRYPTED:
        raise WrongPasswordError("Wrong password")
    return reader


def _ensure_new_output(output_file: Path) -> None:
    """Reject every existing directory entry, including dangling symlinks."""
    try:
        output_file.lstat()
    except FileNotFoundError:
        return
    raise FileExistsError(
        errno.EEXIST, "Refusing to overwrite existing output", str(output_file)
    )


@contextmanager
def _new_output_path(output_file: Path) -> Iterator[Path]:
    """Stage a complete file and publish it without replacing a racing writer."""
    _ensure_new_output(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".pdf-toolkit-", dir=output_file.parent) as staging:
        staged_file = Path(staging) / "output"
        yield staged_file
        # A hard link never replaces an existing destination. Do not fall back
        # to replacing rename/write operations on unsupported filesystems.
        os.link(staged_file, output_file)


class PDFToolkit:
    """PDF核心功能处理类"""

    @staticmethod
    def merge_pdfs(
        input_paths: Iterable[Union[str, Path]],
        output_path: Union[str, Path],
        password: Optional[str] = None,
    ) -> None:
        """
        合并多个 PDF 文件为一个文件，不覆盖已有目标。

        :param input_paths: 输入 PDF 文件路径列表
        :param output_path: 输出 PDF 文件路径
        :param password: 可选。仅在输入文件加密时用于解密
        :raises TypeError: input_paths 是单个路径，而不是路径列表
        :raises ValueError: input_paths 为空
        :raises FileExistsError: 目标已存在（包括符号链接或目录）
        :raises WrongPasswordError: 加密文件的密码不正确
        """
        # A bare string or path is iterable, but it is one path, not a list of
        # paths. Iterating it would merge one-character filenames.
        if isinstance(input_paths, (str, bytes, bytearray)) or not isinstance(
            input_paths, Iterable
        ):
            raise TypeError(
                "input_paths must be an iterable of PDF paths, not a single path"
            )
        output_p = Path(output_path)
        _ensure_new_output(output_p)
        paths = list(input_paths)
        if not paths:
            raise ValueError("input_paths must contain at least one PDF file")
        merger = PdfMerger()
        # PdfMerger reads PdfReader objects during write(); keep them alive.
        opened_readers: List[PdfReader] = []
        try:
            for path in paths:
                if password is None:
                    merger.append(str(path))
                else:
                    reader = _open_reader(path, password)
                    opened_readers.append(reader)
                    merger.append(reader)
            with _new_output_path(output_p) as staged_file:
                # Own the stream so it is closed even if serialization fails.
                with staged_file.open("wb") as stream:
                    merger.write(stream)
        finally:
            merger.close()

    @staticmethod
    def split_pdf(
        input_path: Union[str, Path],
        output_dir: Union[str, Path],
        password: Optional[str] = None,
    ) -> List[Path]:
        """
        将单页或多页 PDF 拆分为单页文件，不覆盖已有目标。

        :param input_path: 输入 PDF 文件路径
        :param output_dir: 输出文件夹路径
        :param password: 可选。仅在输入文件加密时用于解密
        :return: 生成的 PDF 文件路径列表
        :raises FileExistsError: 任一目标已存在（包括符号链接或目录）
        :raises WrongPasswordError: 加密文件的密码不正确

        先检查所有目标，再暂存全部页面。发布时使用不覆盖目标的硬链接；
        如发布中途发生竞争或 I/O 错误，已发布的完整页面会保留。
        输出文件系统必须支持硬链接，不支持时会安全失败。
        """
        reader = _open_reader(input_path, password)
        output_directory = Path(output_dir)
        input_filename = Path(input_path).stem
        generated_files = [
            output_directory / f"{input_filename}_page_{idx}.pdf"
            for idx in range(1, len(reader.pages) + 1)
        ]

        # lstat also detects dangling symlinks, unlike exists(). Check every
        # destination before publishing anything, even a collision on a later page.
        for output_file in generated_files:
            _ensure_new_output(output_file)

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
    def extract_text(
        input_path: Union[str, Path],
        output_txt: Union[str, Path, None] = None,
        password: Optional[str] = None,
    ) -> str:
        """
        提取 PDF 中的文本内容，保存时不覆盖已有目标。

        :param input_path: 输入 PDF 文件路径
        :param output_txt: 可选，将文本写入的 txt 文件路径
        :param password: 可选。仅在输入文件加密时用于解密
        :return: 提取的全部文本
        :raises FileExistsError: 输出目标已存在（包括符号链接或目录）
        :raises WrongPasswordError: 加密文件的密码不正确
        """
        out_p = Path(output_txt) if output_txt else None
        if out_p is not None:
            _ensure_new_output(out_p)
        reader = _open_reader(input_path, password)
        full_text = []

        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            full_text.append(f"--- Page {idx} ---\n{text}")

        extracted_string = "\n\n".join(full_text)

        if out_p is not None:
            with _new_output_path(out_p) as staged_file:
                staged_file.write_text(extracted_string, encoding="utf-8")

        return extracted_string
