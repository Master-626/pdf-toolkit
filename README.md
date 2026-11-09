# PDF Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

一个轻量、高效的全能 PDF 命令行处理工具包，支持 PDF 的合并、拆分、文本提取等常用操作。

## 🌟 功能特性

- 📄 **合并 PDF**：快速合并多个 PDF 文件为一个文件。
- ✂️ **拆分 PDF**：自动按页将 PDF 拆分为独立的单页文件。
- 📝 **提取文本**：提取 PDF 中的纯文本内容，支持直接打印或保存为 TXT。
- 💻 **命令行 & API**：提供易用的 CLI 接口，同时支持在 Python 代码中作为模块调用。

## 📦 安装说明

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/Master-626/pdf-toolkit.git
cd pdf-toolkit

# 本地安装
pip install .
```

## 🚀 使用指南

### 1. 命令行 CLI 使用

安装完成后，可直接在终端使用 `pdf-toolkit` 命令：

终端或重定向输出的编码不支持中文或符号时，命令行会将这些字符显示为转义序列，
避免操作已经完成却因打印提示而报错；PDF 内容和导出的 UTF-8 文本不受影响。

**安全输出**：合并、拆分和文本导出都不会覆盖已有目标，包括目录、符号链接，
以及与输入文件相同的路径或硬链接。遇到冲突时，API 抛出 `FileExistsError`，
CLI 返回非零退出码；请改用新的输出路径。这也保护了检查之后被其他进程创建的目标。

输出先在目标文件系统上暂存完整内容，再通过硬链接发布，写入失败不会留下目标半成品。
因此需要额外磁盘空间和支持硬链接的文件系统；不支持时会报错，不会退回覆盖写入。

**合并 PDF**
```bash
pdf-toolkit merge -i doc1.pdf doc2.pdf -o merged.pdf
```

**拆分 PDF**
```bash
pdf-toolkit split -i doc.pdf -o ./output_folder
```

拆分不会覆盖已有文件。只要任一目标（例如 `doc_page_2.pdf`）已存在，
包括目录或符号链接，就会报错并退出；请改用新的输出目录。
API 对应抛出 `FileExistsError`，CLI 返回非零退出码。

拆分会先暂存所有页面，再逐个发布完整 PDF，避免写入失败留下半成品。
如果发布中途出现其他进程创建同名目标或磁盘错误，已有内容不会被替换，
但此前已发布的完整页面可能保留；检查输出目录并换用新的目录重试。

**提取文本**
```bash
# 在终端直接打印文本内容
pdf-toolkit extract -i doc.pdf

# 将文本保存到 txt 文件
pdf-toolkit extract -i doc.pdf -o extracted.txt
```

### 2. Python API 交互

你也可以在 Python 代码中直接作为库进行调用：

```python
from pdf_toolkit.core import PDFToolkit

# 1. 合并 PDF
PDFToolkit.merge_pdfs(["file1.pdf", "file2.pdf"], "merged.pdf")

# 2. 拆分 PDF
PDFToolkit.split_pdf("input.pdf", "./output_dir")

# 3. 提取文本
text = PDFToolkit.extract_text("input.pdf", output_txt="output.txt")
```

## 🧪 单元测试

项目内置 pytest 测试套件，可通过以下方式运行：

```bash
pip install -e ".[dev]"
pytest
```

## 📄 开源协议

本项目采用 MIT License 协议。
