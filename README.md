# PDF Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

## 简介

`pdf-toolkit` 是一个轻量的 PDF 命令行和 Python 库，用于合并多个 PDF、按页拆分，以及提取文本。合并、拆分和文本导出都不会覆盖已有文件。加密的 PDF 可以用 `--password`（或 API 的 `password`）打开。需要 Python 3.8 及以上。

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Purpose

PDF Toolkit merges PDFs, splits one PDF into single-page files, and extracts text. The same operations are available as the `pdf-toolkit` command and as `PDFToolkit` methods. It is built on PyPDF2 and avoids extra runtime dependencies.

Successful writes never replace an existing file, directory, symlink, or hard link. Output is staged on the destination filesystem and published with a hard link, so a failed write does not leave a half-written target.

## Install

Python 3.8 or newer is required.

```bash
git clone https://github.com/Master-626/pdf-toolkit.git
cd pdf-toolkit
pip install .
```

Install the test and lint tools with:

```bash
pip install -e ".[dev]"
```

After installation the console script is `pdf-toolkit`.

## Command-line usage

Run `pdf-toolkit --help` or `pdf-toolkit <command> --help` for the full text. With no command, the program prints help and exits with status 1. Missing required options exit with status 2. Runtime failures, including existing outputs and a wrong password, exit with status 1.

If the terminal encoding cannot represent the status message, unsupported characters are shown as escape sequences. The PDF bytes and exported UTF-8 text are unchanged.

### merge

Combine PDFs in the order given. `-i` / `--inputs` accepts one or more paths and can be repeated. `-o` / `--output` is required. `-p` / `--password` is optional.

```bash
pdf-toolkit merge -i doc1.pdf doc2.pdf -o merged.pdf
pdf-toolkit merge -i chapter1.pdf -i chapter2.pdf -o book.pdf
pdf-toolkit merge -i secret.pdf notes.pdf -o combined.pdf -p secret
```

Repeating `-i` includes every listed file. A password is used only for encrypted inputs, so an encrypted PDF and a normal PDF can be merged together.

### split

Write one PDF per page into a directory. `-i` / `--input` is the source. `-o` / `--output-dir` is the directory (default `./output`). `-p` / `--password` is optional.

```bash
pdf-toolkit split -i doc.pdf -o ./pages
pdf-toolkit split -i secret.pdf -o ./pages -p secret
```

Page files are named `<stem>_page_<n>.pdf`, starting at 1. `report.pdf` produces `report_page_1.pdf`, `report_page_2.pdf`, and so on. If any destination already exists, including a directory or symlink, the command exits without replacing it.

### extract

Print the text of each page, or save it as UTF-8. `-i` / `--input` is the source. `-o` / `--output` is an optional `.txt` path. `-p` / `--password` is optional.

```bash
pdf-toolkit extract -i doc.pdf
pdf-toolkit extract -i doc.pdf -o extracted.txt
pdf-toolkit extract -i secret.pdf -p secret
```

Each page is prefixed with `--- Page N ---`. Image-only pages contribute an empty body; this tool does not perform OCR.

## Python API

```python
from pdf_toolkit.core import PDFToolkit

PDFToolkit.merge_pdfs(["file1.pdf", "file2.pdf"], "merged.pdf")
PDFToolkit.merge_pdfs(["secret.pdf", "notes.pdf"], "combined.pdf", password="secret")

pages = PDFToolkit.split_pdf("input.pdf", "./output_dir", password="secret")

text = PDFToolkit.extract_text("input.pdf", output_txt="output.txt", password="secret")
print(text)
```

`merge_pdfs` expects an iterable of paths, such as a list, tuple, or generator. Pass `["one.pdf"]` to copy a single file. A bare string is rejected: strings are iterable, and walking one would treat each character as a filename. An empty iterable raises `ValueError` and does not create a file.

`password` is optional. Leave it unset for normal PDFs. For an encrypted PDF, pass the user or owner password. A wrong password raises `PyPDF2.errors.WrongPasswordError` and does not create output. Unencrypted files ignore `password`, which lets one call mix open and encrypted inputs. The merged or split result is not encrypted.

`split_pdf` returns the output paths in page order. `extract_text` always returns the full text. It writes a file only when `output_txt` is set.

## Output safety

Merge, split, and text export refuse to replace an existing target. That includes directories, symlinks (even dangling ones), hard links, and a path that is the same as an input file. The API raises `FileExistsError`. The CLI exits with status 1. Choose a new output path.

The file is written completely in a temporary directory on the destination filesystem, then published with `os.link`. A hard link does not replace an existing name, including a name created by another process after the preflight check. There is no fallback that opens the destination with `"wb"` or renames over it.

The destination filesystem must support hard links and must have room for the staged copy. If it does not, the operation fails and the target is left unchanged.

Split checks every page destination before publishing. If a later page collides, nothing is published. Pages are staged first and then linked one by one. If another process creates a name, or the disk fails, during that publish step, earlier complete pages may remain and existing content is not replaced. Remove those pages or use a new directory and run the command again.

## Tests and lint

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

`pytest` runs the suite under `tests/`. `ruff` checks `src` and `tests` using the settings in `pyproject.toml`. GitHub Actions runs both on Python 3.8 through 3.13.

## License

MIT License. See [LICENSE](LICENSE).
