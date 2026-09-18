import argparse
import sys
from pathlib import Path
from pdf_toolkit.core import PDFToolkit


def main():
    parser = argparse.ArgumentParser(
        description="PDF Toolkit - 一个轻量全能的 PDF 命令行处理工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令帮助")

    # 1. merge
    merge_parser = subparsers.add_parser("merge", help="合并多个 PDF 文件")
    merge_parser.add_argument(
        "-i", "--inputs", nargs="+", required=True, help="需要合并的 PDF 文件路径列表"
    )
    merge_parser.add_argument(
        "-o", "--output", required=True, help="合并后的目标文件路径"
    )

    # 2. split
    split_parser = subparsers.add_parser("split", help="拆分 PDF 文件为单页")
    split_parser.add_argument(
        "-i", "--input", required=True, help="需要拆分的 PDF 文件路径"
    )
    split_parser.add_argument(
        "-o", "--output-dir", default="./output", help="输出文件夹路径（默认：./output）"
    )

    # 3. extract
    extract_parser = subparsers.add_parser("extract", help="提取 PDF 中的文本内容")
    extract_parser.add_argument(
        "-i", "--input", required=True, help="PDF 文件路径"
    )
    extract_parser.add_argument(
        "-o", "--output", help="保存提取文本的 txt 文件路径（可选）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "merge":
            PDFToolkit.merge_pdfs(args.inputs, args.output)
            print(f"✅ 合并完成！已保存至: {args.output}")

        elif args.command == "split":
            files = PDFToolkit.split_pdf(args.input, args.output_dir)
            print(f"✅ 拆分完成！共生成 {len(files)} 个文件，已保存至: {args.output_dir}")

        elif args.command == "extract":
            text = PDFToolkit.extract_text(args.input, args.output)
            if args.output:
                print(f"✅ 文本已提取并保存至: {args.output}")
            else:
                print("--- 提取结果 ---")
                print(text)

    except Exception as e:
        print(f"❌ 发生错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
