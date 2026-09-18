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

**合并 PDF**
```bash
pdf-toolkit merge -i doc1.pdf doc2.pdf -o merged.pdf
```

**拆分 PDF**
```bash
pdf-toolkit split -i doc.pdf -o ./output_folder
```

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
