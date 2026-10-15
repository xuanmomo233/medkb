"""将本地正版教材的指定纸书页渲染为受控发布用 WebP 页图。

示例（病理学第十版 PDF 前置 25 页）：
python scripts/render_textbook_pages.py --pdf ".../03.《病理学（第10版）》.pdf" \
  --output-dir ".../rendered/rjws-pathology-10" --pdf-page-offset 25 \
  --pages 5-10,41-55,59-76,90-123
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf
from PIL import Image


def page_numbers(spec: str) -> list[int]:
    result: set[int] = set()
    for part in spec.split(","):
        try:
            left, *right = part.strip().split("-", maxsplit=1)
            first = int(left)
            last = int(right[0]) if right else first
        except ValueError as error:
            raise argparse.ArgumentTypeError(f"无效页码范围：{part}") from error
        if first < 1 or last < first:
            raise argparse.ArgumentTypeError(f"无效页码范围：{part}")
        result.update(range(first, last + 1))
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="渲染受控教材页图")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pdf-page-offset", type=int, required=True, help="PDF 一页对应的纸书页码偏移")
    parser.add_argument("--pages", type=page_numbers, required=True, help="例如 5-10,41-55")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的页图")
    args = parser.parse_args()
    if args.dpi < 72 or args.dpi > 300:
        parser.error("dpi 必须在 72-300 之间")
    if not args.pdf.is_file():
        parser.error(f"PDF 不存在：{args.pdf}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    scale = args.dpi / 72
    with pymupdf.open(args.pdf) as document:
        for book_page in args.pages:
            pdf_index = book_page + args.pdf_page_offset - 1
            if not 0 <= pdf_index < document.page_count:
                parser.error(f"纸书第 {book_page} 页超出 PDF 范围")
            output = args.output_dir / f"page_{book_page:04d}.webp"
            if output.is_file() and not args.overwrite:
                print(f"保留 {output}")
                continue
            pixmap = document.load_page(pdf_index).get_pixmap(
                matrix=pymupdf.Matrix(scale, scale), alpha=False,
            )
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            image.save(output, "WEBP", quality=84, method=6)
            print(output)


if __name__ == "__main__":
    main()
