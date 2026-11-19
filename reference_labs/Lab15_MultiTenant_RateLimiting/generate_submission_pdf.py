"""Render the project README as a clean, print-ready lab submission PDF."""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT = 52
TOP = 790
BOTTOM = 52


def _ascii(text: str) -> str:
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text.encode("ascii", "replace").decode("ascii")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _markdown_blocks(markdown: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(("body", " ".join(paragraph)))
            paragraph.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            flush_paragraph()
            if code:
                blocks.extend(("code", code_line) for code_line in code_lines)
                code_lines.clear()
            code = not code
            continue
        if code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            continue
        if line.startswith("# "):
            flush_paragraph()
            blocks.append(("title", line[2:].strip()))
        elif line.startswith("## "):
            flush_paragraph()
            blocks.append(("heading", line[3:].strip()))
        elif line.startswith("- "):
            flush_paragraph()
            blocks.append(("bullet", "- " + line[2:].strip()))
        else:
            paragraph.append(line.strip())

    flush_paragraph()
    if code_lines:
        blocks.extend(("code", code_line) for code_line in code_lines)
    return blocks


def _layout(markdown: str) -> list[list[tuple[str, str]]]:
    laid_out: list[tuple[str, str]] = []
    widths = {"title": 64, "heading": 78, "body": 94, "bullet": 88, "code": 88}
    for style, text in _markdown_blocks(markdown):
        text = _ascii(text)
        if style == "body":
            text = re.sub(r"`([^`]*)`", r"\1", text)
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        wrapped = textwrap.wrap(
            text,
            width=widths[style],
            subsequent_indent="    " if style == "bullet" else "",
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        laid_out.extend((style, part) for part in wrapped)
        laid_out.append(("space", ""))

    pages: list[list[tuple[str, str]]] = [[]]
    y = TOP
    for style, text in laid_out:
        if style == "title":
            font_size, leading, gap = 14, 18, 8
        elif style == "heading":
            font_size, leading, gap = 10, 14, 5
        elif style == "code":
            font_size, leading, gap = 8, 11, 0
        elif style == "space":
            font_size, leading, gap = 0, 5, 0
        else:
            font_size, leading, gap = 9, 12, 0
        if y - leading < BOTTOM and pages[-1]:
            pages.append([])
            y = TOP
        pages[-1].append((style, text))
        y -= leading + gap
    return [page for page in pages if page]


def _pdf_string(pages: list[list[tuple[str, str]]]) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{6 + 2 * i} 0 R".encode("ascii") for i in range(len(pages)))
        + f"] /Count {len(pages)} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]

    for page_number, page in enumerate(pages):
        page_id = 6 + page_number * 2
        content_id = page_id + 1
        commands = ["BT"]
        y = TOP
        for style, text in page:
            if style == "title":
                font, size, leading, gap = "F2", 14, 18, 8
            elif style == "heading":
                font, size, leading, gap = "F2", 10, 14, 5
            elif style == "code":
                font, size, leading, gap = "F3", 8, 11, 0
            elif style == "space":
                font, size, leading, gap = "F1", 1, 5, 0
            else:
                font, size, leading, gap = "F1", 9, 12, 0
            commands.extend(
                [
                    f"/{font} {size} Tf",
                    f"{LEFT} {y} Td",
                    f"({_escape(text)}) Tj",
                    f"{-LEFT} {-y} Td",
                ]
            )
            y -= leading + gap
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body + b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def write_pdf(source: Path, destination: Path) -> None:
    markdown = source.read_text(encoding="utf-8")
    destination.write_bytes(_pdf_string(_layout(markdown)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("README.md"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("LAB_15_G.RAJA SIMHA REDDY_24BTRCL070.pdf"),
    )
    args = parser.parse_args()
    write_pdf(args.source, args.output)
    print(f"Created {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
