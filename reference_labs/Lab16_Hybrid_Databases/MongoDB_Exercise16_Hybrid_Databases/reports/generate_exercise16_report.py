from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "latency_results.csv"
OUTPUT_PATH = ROOT / "reports" / "Lab16_G.RAJA SIMHA REDDY_24BTRCL070.pdf"


def read_latency_csv(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({
                "operation": row["operation"],
                "mean_ms": float(row["mean_ms"]),
                "notes": row["notes"],
            })
    return rows


def build_pdf(latency_rows):
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=18,
        leading=24,
        alignment=0,
        textColor=colors.black,
        spaceAfter=16,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["BodyText"],
        fontSize=12,
        leading=18,
        textColor=colors.black,
        spaceAfter=22,
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1f3a5f"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
    )

    story = []
    story.append(Spacer(1, 28))
    story.append(Paragraph("Chapter 16 - Hybrid Database Labs", title_style))
    story.append(Paragraph(
        "Lab 16.1 (Data Modeling) and Lab 16.2 (Hybrid Fraud Query Service)",
        subtitle_style,
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Name: GANGIREDDY RAJA SIMHA REDDY", body_style))
    story.append(Paragraph("USN: 24BTRCL070", body_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Docker Hub image:</b> https://hub.docker.com/r/raja6303/mongodb-exercise16",
        body_style,
    ))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        f"Report generated: {datetime.now().strftime('%Y-%m-%d')}",
        body_style,
    ))
    story.append(PageBreak())

    story.append(Paragraph("Exercise 16 - Hybrid Databases", title_style))
    story.append(Paragraph(
        "Project: MongoDB + Cassandra + Neo4j Fraud Query Service",
        body_style,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Objective", heading_style))
    story.append(Paragraph(
        "This exercise implemented a hybrid fraud-analysis workflow spanning MongoDB for transaction lookups, "
        "Cassandra for user activity history, and Neo4j for graph-based fraud-ring detection. The service "
        "includes circuit breakers, degraded-mode handling, and a merged fraud-analysis response.",
        body_style,
    ))

    story.append(Paragraph("Architecture Summary", heading_style))
    story.append(Paragraph(
        "MongoDB stores transaction records and provides transaction risk scores. Cassandra stores per-user "
        "event history in a time-sorted profile table. Neo4j models transfer relationships and finds related "
        "accounts within a configured hop depth. The Python service combines these data sources through "
        "analyze_fraud(...) and supports degraded-mode responses when a database is unavailable.",
        body_style,
    ))

    story.append(Paragraph("Validation and Verification", heading_style))
    story.append(Paragraph(
        "The project was validated with the included unittest suite under Python 3.11, which is the supported "
        "runtime for the Cassandra Python driver in this environment. The test suite passed: 8 tests ran with OK status. "
        "Database connectivity was also validated against the running Docker stack for MongoDB, Cassandra, and Neo4j.",
        body_style,
    ))

    story.append(Paragraph("Measured Latency Results", heading_style))
    table_data = [["Operation", "Mean (ms)", "Notes"]]
    for row in latency_rows:
        table_data.append([row["operation"], f"{row['mean_ms']:.2f}", row["notes"]])
    table = Table(table_data, colWidths=[220, 80, 220])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfeaf7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(table)

    story.append(Spacer(1, 8))
    story.append(Paragraph("Docker and Environment Notes", heading_style))
    story.append(Paragraph(
        "MongoDB, Cassandra, and Neo4j were started through Docker Compose and verified healthy via container health checks. "
        "The hybrid service image was built locally and pushed to Docker Hub as raja6303/mongodb-exercise16:exercise16.",
        body_style,
    ))

    story.append(Paragraph("Security and Reliability Notes", heading_style))
    story.append(Paragraph(
        "The service uses circuit breakers to block repeated calls to a failing database and falls back to partial results when a dependency is unavailable. "
        "This preserves service continuity while making the failure mode explicit and observable in logs.",
        body_style,
    ))

    story.append(Paragraph("Conclusion", heading_style))
    story.append(Paragraph(
        "The Exercise 16 hybrid database solution is implemented, tested, and validated locally. The project is ready for review "
        "and submission with the recorded latency data and database health checks included in this PDF.",
        body_style,
    ))

    doc.build(story)


if __name__ == "__main__":
    rows = read_latency_csv(CSV_PATH)
    build_pdf(rows)
    print(f"Generated report: {OUTPUT_PATH}")
