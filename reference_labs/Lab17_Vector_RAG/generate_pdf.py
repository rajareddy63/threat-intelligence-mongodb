"""Create a submission PDF with benchmark results when available."""

from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from statistics import mean
from typing import Any

from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


load_dotenv(Path(__file__).with_name(".env"), override=False)

OUTPUT_PATH = Path(os.getenv("SUBMISSION_PDF_PATH", "Exercise_17_Submission.pdf"))
RESULTS_PATH = Path(os.getenv("BENCHMARK_RESULTS_PATH", "benchmark_results.json"))
IMAGE_NAME = os.getenv("DOCKER_IMAGE", "yourusername/mongodb-rag-lab17:latest")
IMAGE_REPOSITORY = IMAGE_NAME.split("@", maxsplit=1)[0].rsplit(":", maxsplit=1)[0]
DOCKER_UPLOAD_STATUS = os.getenv(
    "DOCKER_UPLOAD_STATUS",
    "Not verified: Docker Hub latest manifest has not been confirmed.",
)
DOCKER_HUB_URL = (
    f"https://hub.docker.com/r/{IMAGE_REPOSITORY}"
    if "yourusername" not in IMAGE_REPOSITORY
    else "<YOUR_DOCKER_HUB_IMAGE_URL>"
)
STUDENT_NAME = "GANGIREDDY RAJA SIMHA REDDY"
STUDENT_USN = "24BTRCL070"


def load_benchmark_rows(results_path: Path = RESULTS_PATH) -> list[list[str]]:
    if not results_path.exists():
        return [
            ["HNSW", "Not run", "Not run", "Not run"],
            ["IVF", "Not run", "Not run", "Not run"],
        ]
    report: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))
    by_name = {row["index"]: row for row in report.get("results", [])}
    rows = []
    for name in ("HNSW", "IVF"):
        result = by_name.get(name)
        if result is None:
            rows.append([name, "Not available", "Not available", "Not available"])
            continue
        rows.append(
            [
                name,
                f"{result['build_time_seconds']:.4f} s",
                f"{result['avg_query_latency_ms']:.4f} ms",
                f"{result['recall_at_20_percent']:.2f}%",
            ]
        )
    return rows


def load_benchmark_output(results_path: Path = RESULTS_PATH) -> str:
    if not results_path.exists():
        return "Benchmark has not been run; no measurements are available."

    report: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))
    results = report.get("results", [])
    if not results:
        return "The benchmark report contains no index measurements."

    lines = [
        "$ Benchmark report: benchmark_results.json",
        (
            f"documents={report.get('document_count', 'n/a')}  "
            f"dimensions={report.get('embedding_dimensions', 'n/a')}  "
            f"queries={report.get('query_count', 'n/a')}  "
            f"top_k={report.get('top_k', 'n/a')}  "
            f"metric={report.get('metric', 'n/a')}"
        ),
        "",
        f"{'Index':<8} {'Build (s)':>12} {'Query (ms)':>13} {'Recall@20':>12}",
        "-" * 48,
    ]
    for result in results:
        lines.append(
            f"{result['index']:<8} "
            f"{result['build_time_seconds']:>12.4f} "
            f"{result['avg_query_latency_ms']:>13.4f} "
            f"{result['recall_at_20_percent']:>11.2f}%"
        )
    lines.extend(
        [
            "",
            (
                f"Mean: build={mean(r['build_time_seconds'] for r in results):.4f}s, "
                f"query={mean(r['avg_query_latency_ms'] for r in results):.4f}ms, "
                f"Recall@20={mean(r['recall_at_20_percent'] for r in results):.2f}%"
            ),
        ]
    )
    return "\n".join(lines)


def build_pdf(output_path: Path = OUTPUT_PATH, results_path: Path = RESULTS_PATH) -> None:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReferenceTitle",
            parent=styles["Title"],
            alignment=0,
            textColor=colors.black,
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReferenceSubtitle",
            parent=styles["BodyText"],
            fontSize=10,
            leading=13,
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReferenceBody",
            parent=styles["BodyText"],
            fontSize=9.5,
            leading=13,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReferenceHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.black,
            spaceBefore=9,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Terminal",
            fontName="Courier",
            fontSize=7.2,
            leading=9,
            textColor=colors.white,
        )
    )
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="Exercise 17 - MongoDB Vector Search and RAG",
        author=STUDENT_NAME,
    )

    escaped_url = escape(DOCKER_HUB_URL)
    if DOCKER_HUB_URL.startswith("https://"):
        docker_url = (
            f"<b>Docker Hub URL:</b> "
            f"<link href=\"{escape(DOCKER_HUB_URL, quote=True)}\">{escaped_url}</link>"
        )
    else:
        docker_url = f"<b>Docker Hub URL:</b> {escaped_url}"

    story = [
        Paragraph(
            "Exercise 17 - MongoDB Vector Search and RAG",
            styles["ReferenceTitle"],
        ),
        Paragraph(
            "Lab 17.1 (RAG and Conversation Memory) and Lab 17.2 (HNSW vs. IVF)",
            styles["ReferenceSubtitle"],
        ),
        Paragraph(f"Name: {STUDENT_NAME}", styles["ReferenceBody"]),
        Paragraph(f"USN: {STUDENT_USN}", styles["ReferenceBody"]),
        Paragraph(docker_url, styles["ReferenceBody"]),
        Spacer(1, 5),
        Paragraph("Lab 17.1 - RAG and conversation memory", styles["ReferenceHeading"]),
        Paragraph(
            "Four threat-intelligence documents are split into overlapping 100-word "
            "chunks and stored in MongoDB Atlas. The application retrieves the top "
            "three matches with vector search and includes the user's five most recent "
            "messages in the response context. Embeddings use Voyage AI when configured, "
            "otherwise the configured Sentence Transformers model is used.",
            styles["ReferenceBody"],
        ),
        Paragraph("Lab 17.2 - HNSW vs. IVF benchmark", styles["ReferenceHeading"]),
        Paragraph(
            "The benchmark compares FAISS HNSW (M=16, efConstruction=64) and IVF "
            "(nlist=100, nprobe=10) using normalized 384-dimensional vectors and "
            "inner product for cosine similarity. It uses 5,000 generated documents, "
            "100 queries, and exact top-20 results to calculate Recall@20.",
            styles["ReferenceBody"],
        ),
    ]
    table_data = [
        ["Index", "Build Time", "Avg Query Latency", "Recall@20"],
        *load_benchmark_rows(results_path),
    ]
    table = Table(
        table_data,
        colWidths=[30 * mm, 38 * mm, 53 * mm, 37 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            Spacer(1, 5),
            table,
            Paragraph("Docker image status", styles["ReferenceHeading"]),
            Paragraph(escape(DOCKER_UPLOAD_STATUS), styles["ReferenceBody"]),
            PageBreak(),
            Paragraph("Demonstration output", styles["ReferenceTitle"]),
            Paragraph(
                "Recorded HNSW and IVF measurements from the benchmark report.",
                styles["ReferenceSubtitle"],
            ),
        ]
    )
    terminal = Table([[Preformatted(load_benchmark_output(results_path), styles["Terminal"])]])
    terminal.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111111")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend(
        [
            terminal,
            Spacer(1, 8),
            Paragraph(
                "The figures are read directly from benchmark_results.json; if that "
                "file is unavailable, the PDF identifies the benchmark as not run.",
                styles["ReferenceBody"],
            ),
        ]
    )
    document.build(story)


if __name__ == "__main__":
    build_pdf()
    print(f"Generated {OUTPUT_PATH.resolve()}")
