"""Build the submission PDF and vector benchmark charts from recorded JSON results."""
from __future__ import annotations

import html
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PDF_NAME = "Exercise_18_Final_Submission.pdf"
DB_LABELS = {"mongodb": "MongoDB", "cassandra": "Apache Cassandra", "neo4j": "Neo4j"}
QUERY_LABELS = {"threat_history": "Threat history", "target_and_spread": "Target and spread", "daily_volume": "Daily analytics"}


class ArchitectureDiagram(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = 500, 155

    def draw(self):
        c = self.canv
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#243746"))
        c.roundRect(185, 107, 130, 32, 5, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.drawCentredString(250, 119, "Python benchmark runner")
        boxes = [(8, "MongoDB", "Document + compound indexes", "#168A72"), (183, "Cassandra", "Query-first wide rows", "#C56A36"), (358, "Neo4j", "Threat/Target graph", "#3478A6")]
        for x, name, detail, color in boxes:
            c.setFillColor(colors.HexColor(color))
            c.roundRect(x, 24, 132, 48, 5, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(x + 66, 54, name)
            c.setFont("Helvetica", 7.5)
            c.drawCentredString(x + 66, 39, detail)
            c.setStrokeColor(colors.HexColor("#6B7F8D"))
            c.setLineWidth(1.2)
            c.line(250, 106, x + 66, 73)
        c.setFillColor(colors.HexColor("#243746"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(250, 5, "Shared synthetic event stream | Docker Compose | Persistent database volumes")


class BarChart(Flowable):
    def __init__(self, labels, values, title, suffix=" ms"):
        super().__init__()
        self.labels, self.values, self.title, self.suffix = labels, values, title, suffix
        self.width, self.height = 500, max(120, 34 * len(labels) + 52)

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor("#243746"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(0, self.height - 15, self.title)
        usable = 310
        maximum = max((value or 0 for value in self.values), default=0) or 1
        palette = ("#168A72", "#C56A36", "#3478A6")
        for i, (label, value) in enumerate(zip(self.labels, self.values)):
            y = self.height - 44 - i * 32
            c.setFillColor(colors.HexColor("#243746"))
            c.setFont("Helvetica", 8)
            c.drawString(0, y + 3, label[:22])
            if value is not None:
                width = max(2, usable * value / maximum)
                c.setFillColor(colors.HexColor(palette[i % len(palette)]))
                c.roundRect(145, y - 2, width, 13, 2, fill=1, stroke=0)
                c.setFillColor(colors.HexColor("#243746"))
                c.drawString(153 + width, y + 1, f"{value:,.2f}{self.suffix}")
            else:
                c.setFillColor(colors.HexColor("#6B7F8D"))
                c.drawString(150, y + 1, "Not measured")


def _format_metric(value, runs, requested, unit):
    if value is None:
        return "Not measured"
    return f"{value:,.2f}{unit} ({runs}/{requested} runs)"


def _create_svg(path: Path, title: str, series: list[tuple[str, float | None]], unit: str) -> None:
    width, height, left, top, row_h, bar_w = 720, 90 + len(series) * 46, 190, 48, 46, 360
    max_value = max((v or 0 for _, v in series), default=0) or 1
    palette = ("#168A72", "#C56A36", "#3478A6")
    rows = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#ffffff"/>', f'<text x="24" y="30" font-family="Arial" font-size="18" font-weight="bold" fill="#243746">{html.escape(title)}</text>']
    for i, (label, value) in enumerate(series):
        y = top + i * row_h
        rows.append(f'<text x="24" y="{y + 17}" font-family="Arial" font-size="13" fill="#243746">{html.escape(label)}</text>')
        if value is None:
            rows.append(f'<text x="{left}" y="{y + 17}" font-family="Arial" font-size="12" fill="#6B7F8D">Not measured</text>')
        else:
            length = max(2, bar_w * value / max_value)
            rows.append(f'<rect x="{left}" y="{y}" width="{length:.1f}" height="22" rx="3" fill="{palette[i % len(palette)]}"/>')
            rows.append(f'<text x="{left + length + 8:.1f}" y="{y + 16}" font-family="Arial" font-size="12" fill="#243746">{value:,.2f}{html.escape(unit)}</text>')
    rows.append('</svg>')
    path.write_text("\n".join(rows), encoding="utf-8")


def build_report(results_path: Path | str = "results/benchmark_results.json", output_dir: Path | str = "results") -> Path:
    results_path, output_dir = Path(results_path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
    benchmark = data.get("benchmark", {})
    db_results = benchmark.get("databases", {})
    database_status = data.get("database_status", {})
    dataset_requested = data.get("dataset_records_requested")
    dataset_text = f"{dataset_requested:,}" if isinstance(dataset_requested, int) else "Not recorded"
    requested_runs = benchmark.get("runs_requested", 10)
    db_order = ("mongodb", "cassandra", "neo4j")
    query_rows = [["Database", "Threat history", "Target and spread", "Daily analytics", "Insert throughput"]]
    for db in db_order:
        item = db_results.get(db, {})
        queries = item.get("queries", {})
        query_rows.append([
            DB_LABELS[db],
            _format_metric(queries.get("threat_history", {}).get("median_latency_ms"), queries.get("threat_history", {}).get("successful_runs", 0), requested_runs, " ms"),
            _format_metric(queries.get("target_and_spread", {}).get("median_latency_ms"), queries.get("target_and_spread", {}).get("successful_runs", 0), requested_runs, " ms"),
            _format_metric(queries.get("daily_volume", {}).get("median_latency_ms"), queries.get("daily_volume", {}).get("successful_runs", 0), requested_runs, " ms"),
            _format_metric(item.get("median_insert_throughput_records_per_second"), item.get("successful_insert_runs", 0), requested_runs, " records/s"),
        ])
    latency_series = [(DB_LABELS[db], db_results.get(db, {}).get("queries", {}).get("threat_history", {}).get("median_latency_ms")) for db in db_order]
    throughput_series = [(DB_LABELS[db], db_results.get(db, {}).get("median_insert_throughput_records_per_second")) for db in db_order]
    _create_svg(output_dir / "benchmark_query_latency.svg", "Threat history median latency", latency_series, " ms")
    _create_svg(output_dir / "benchmark_insert_throughput.svg", "Measured insert batch throughput", throughput_series, " records/s")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.HexColor("#243746"), alignment=0, spaceAfter=9))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#168A72"), spaceBefore=9, spaceAfter=8))
    styles.add(ParagraphStyle(name="Subsection", parent=styles["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#243746"), spaceBefore=7, spaceAfter=4))
    styles.add(ParagraphStyle(name="BodyTight", parent=styles["BodyText"], fontSize=9, leading=13, spaceAfter=6))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7.5, leading=10))
    destination = output_dir / PDF_NAME

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D8E0E5"))
        canvas.line(0.65 * inch, 0.55 * inch, 7.85 * inch, 0.55 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7F8D"))
        canvas.drawString(0.68 * inch, 0.38 * inch, "Exercise 18 | Comparative Capstone Lab")
        canvas.drawRightString(7.82 * inch, 0.38 * inch, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=0.65 * inch, leftMargin=0.65 * inch, topMargin=0.65 * inch, bottomMargin=0.75 * inch, title="Exercise 18 - Comparative Capstone Lab", author="GANGIREDDY RAJA SIMHA REDDY")
    story = [
        Spacer(1, 0.12 * inch),
        Paragraph("Chapter 18 - Comparative Capstone Lab", styles["CoverTitle"]),
        Paragraph("Lab 18.1 (Comparative System) and Lab 18.2 (Performance Analysis)", styles["BodyText"]),
        Spacer(1, 0.22 * inch),
        Paragraph("Name: GANGIREDDY RAJA SIMHA REDDY", styles["BodyText"]),
        Paragraph("USN: 24BTRCL070", styles["BodyText"]),
        Paragraph("Submission date: 15 November 2026", styles["BodyText"]),
        Spacer(1, 0.1 * inch),
        Paragraph("<b>Docker Hub URL:</b> <link href='https://hub.docker.com/r/raja6303/mongodb-exercise18' color='#176B87'>https://hub.docker.com/r/raja6303/mongodb-exercise18</link>", styles["BodyText"]),
        Spacer(1, 0.15 * inch),
        Paragraph("This report distinguishes confirmed load counts, measured but incomplete-run timings, and scalability estimates.", styles["Small"]),
        PageBreak(),
    ]

    actual_push_note = next((note for note in data.get("notes", []) if note.startswith("Docker Hub push verified:")), "Docker Hub publication was not verified.")
    demo_rows = [
        [Paragraph("Demonstration check", styles["Small"]), Paragraph("Observed result", styles["Small"])],
        ["Dataset load", f"{dataset_text} requested; confirmed load counts: " + ", ".join(f"{DB_LABELS[db]} {database_status.get(db, {}).get('loaded_records', 0):,}" for db in db_order) + "."],
        ["Query repetitions", f"{requested_runs} runs were recorded for the attempted workload. Because no database confirmed the full load, these timings are partial/unconfirmed and are not a valid 100K comparison."],
        ["Docker Hub", actual_push_note],
    ]
    demo_table = Table(demo_rows, colWidths=[1.55 * inch, 5.55 * inch], repeatRows=1)
    demo_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243746")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("LEADING", (0, 0), (-1, -1), 11), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8E0E5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F7")]), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [Paragraph("Demonstration output", styles["Section"]), Paragraph("The following is a concise summary of recorded execution and remote publication evidence. No synthetic screenshot is used.", styles["BodyTight"]), demo_table, PageBreak()]

    story += [Paragraph("1. Executive Summary", styles["Section"]), Paragraph("This capstone implements one synthetic threat-intelligence event workload across three database models. MongoDB stores flexible event documents, Cassandra uses query-specific denormalized tables, and Neo4j models Threat and Target nodes connected by TARGETS relationships. The Docker Compose workflow provisions persistent database services and runs schema setup, loading, measurements, and report generation.", styles["BodyTight"]), Paragraph(f"Requested workload: {dataset_text} records; benchmark repetitions: {requested_runs}. These are requested settings, not proof of successful completion. The measured outcome for each service appears below with load-completion status.", styles["BodyTight"]), Paragraph("2. Objectives and Architecture", styles["Section"]), Paragraph("The objective is to compare history lookup, target-level aggregation, daily volume analytics, and measured batched insert throughput using a common generated input and explicit database-specific schema choices.", styles["BodyTight"]), ArchitectureDiagram(), Spacer(1, 8), Paragraph("3. Methodology", styles["Section"]), Paragraph("The seeded generator produces repeatable synthetic IPv4, domain, URL, and SHA-256 indicators across five source labels, multiple targets, severity levels, and a rolling one-year event window. Each database receives the same in-memory records. Query latency is measured with a monotonic timer; the reported statistic is the median of successful repetitions. Insert throughput measures the configured batch size written repeatedly through each adapter's bulk-write path. This is not a single-row latency measurement. Environment details and successful counts are persisted in the JSON artifact.", styles["BodyTight"]), Paragraph("A database that fails connection, initialization, loading, or a query is reported as unavailable or partial in the artifacts rather than assigned a fabricated value. Measurements are specific to this machine, container configuration, data, and indexes; they are not universal rankings.", styles["BodyTight"]), Paragraph("4. Schema Design Comparison", styles["Section"])]

    schema_data = [["Database", "Record model and access paths"], ["MongoDB", "threats collection; unique threat_id; compound indicator/observed_at and target/observed_at indexes; observed_at/source index for date filtering."], ["Cassandra", "Three denormalized tables partitioned by indicator, target, or day. Clustering columns order history and support target/day scans without secondary-index dependence."], ["Neo4j", "Threat nodes with indexed indicator, target, and observed_at fields; Target nodes linked by TARGETS; uniqueness constraint on threat_id."]]
    table = Table(schema_data, colWidths=[1.05 * inch, 5.85 * inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243746")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("LEADING", (0, 0), (-1, -1), 10), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E0E5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F7")]), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(table)
    story += [Paragraph("5. Query Performance Comparison", styles["Section"]), Paragraph("Actual measurements only. Latency is median milliseconds; insert throughput is the median records/second across repeated batches. Successful run counts appear beside measurements. 'Not measured' means this execution produced no usable figure.", styles["BodyTight"])]
    performance = Table(query_rows, colWidths=[0.85 * inch, 1.38 * inch, 1.38 * inch, 1.28 * inch, 1.35 * inch], repeatRows=1)
    performance.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243746")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7), ("LEADING", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E0E5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F7")]), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    load_rows = [["Database", "Confirmed loaded", "Load status"]]
    for db in db_order:
        state = database_status.get(db, {})
        count = state.get("loaded_records", 0)
        complete = count == dataset_requested and not state.get("load_error")
        error = state.get("load_error") or ""
        status_text = "Complete" if complete else f"Incomplete; {error[:220]}" if error else "Incomplete; no confirmed full load"
        load_rows.append([DB_LABELS[db], f"{count:,} / {dataset_text}", Paragraph(html.escape(status_text), styles["Small"])])
    load_table = Table(load_rows, colWidths=[1.35 * inch, 1.5 * inch, 4.25 * inch], repeatRows=1)
    load_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243746")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E0E5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F7")]), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [performance, Spacer(1, 6), Paragraph("Load completeness (a failed loader may have left partial writes; counts below are only confirmed completed loads):", styles["Small"]), load_table, Spacer(1, 8), BarChart([x[0] for x in latency_series], [x[1] for x in latency_series], "Threat history median latency"), Spacer(1, 8), BarChart([x[0] for x in throughput_series], [x[1] for x in throughput_series], "Measured batch insert throughput", " records/s"), Paragraph("6. Developer Experience and Ergonomics", styles["Section"]), Paragraph("MongoDB offers a natural document API and flexible fields, with aggregation pipelines for summaries. Cassandra provides predictable partition-key reads and concurrent prepared writes, but denormalization and partition sizing must be designed around queries. Neo4j makes relationship traversals and graph patterns expressive; Cypher constraints and transactional UNWIND batches simplify the graph load but introduce node/relationship modeling choices.", styles["BodyTight"]), PageBreak()]

    story += [Paragraph("7. Scalability Assessment (Estimates)", styles["Section"]), Paragraph("The following are planning estimates, not executed tests. They assume the same average record shape and indexed access patterns; storage excludes replication, backups, logs, and filesystem overhead. Actual sizing must be derived from measured serialized data, index growth, retention, compression, and workload concurrency.", styles["BodyTight"])]
    scale_rows = [["Dataset", "Planning data size*", "Deployment note (estimate)"]]
    for count, size in (("1M", "~0.5-1.5 GB"), ("10M", "~5-15 GB"), ("100M", "~50-150 GB")):
        note = {"1M": "Single-node evaluation is plausible; validate index and cache fit.", "10M": "Plan sharding/replication and benchmark partition balance.", "100M": "Distributed deployment, capacity testing, and operational SLOs required."}[count]
        scale_rows.append([count, size, note])
    scale = Table(scale_rows, colWidths=[0.9 * inch, 1.6 * inch, 4.4 * inch], repeatRows=1)
    scale.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243746")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8E0E5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F7")]), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [scale, Paragraph("*Order-of-magnitude planning range only; validate against the actual data and selected database's index/replication overhead.", styles["Small"]), Paragraph("Horizontal scaling", styles["Subsection"]), Paragraph("MongoDB: shard the collection on a workload-appropriate shard key and deploy replica sets. Cassandra: add nodes to the ring and set replication factor; choose partition keys to avoid hotspots. Neo4j Community in this Compose lab is single-instance; production horizontal scale depends on Enterprise clustering or an application-level graph partitioning design. Replication and sharding do not remove the need for workload-specific testing.", styles["BodyTight"]), Paragraph("8. Hardware and Estimated Resources", styles["Section"]), Paragraph("The Compose defaults are a local demonstration profile, not production capacity guidance. Cassandra is configured with a 1 GB heap, Neo4j with a 1 GB maximum heap plus 512 MB page cache, and MongoDB uses its image defaults. A practical local run should have at least 8 GB RAM available to Docker and several CPU cores; allow additional memory and disk for retained volumes, the Python process, database indexes, and concurrent services. Record the host CPU, memory, Docker limits, and disk type when comparing runs.", styles["BodyTight"]), Paragraph("9. Backup and Monitoring", styles["Section"]), Paragraph("For production, schedule and restore-test MongoDB replica-set backups (mongodump or managed snapshots), Cassandra snapshots plus incremental commit-log archiving, and Neo4j online backups or supported volume snapshots. Protect encryption keys and credentials separately. Monitor latency percentiles, errors, connection pools, CPU, memory, disk, replication/repair state, and storage growth. Use database-native metrics and alert on backup freshness and restore-test failures. The lab Compose volumes are persistence for demonstration, not a backup strategy.", styles["BodyTight"]), Paragraph("10. Final Recommendations", styles["Section"]), Paragraph("Select the store from access patterns, not a single local benchmark: MongoDB is a balanced default for evolving threat documents and ad hoc filters; Cassandra fits sustained high-volume writes and known, partition-key-driven lookups; Neo4j is the strongest fit when analyst workflows depend on traversing relationships among indicators, targets, campaigns, and sources. Re-run the included workload with production-shaped concurrency, retention, replication, and data distributions before making a capacity or product decision.", styles["BodyTight"]), Paragraph("11. Reproduction and Submission", styles["Section"]), Paragraph("Start the services and execute the default 100,000-record, 10-run workflow with: docker compose up --build. Results are written to results/benchmark_results.json and .csv; the PDF and SVG charts are written to results/. To choose a smaller smoke-test dataset, use: $env:THREAT_RECORDS='1000'; docker compose up --build. To stop services while retaining data: docker compose down. The local demo Neo4j password is configured in docker-compose.yml and must be replaced for any non-lab use.", styles["BodyTight"]), Paragraph("Docker Hub repository: https://hub.docker.com/r/[DOCKERHUB_USERNAME]/mongodb-exercise18 (replace with the verified published repository URL; publication status is not inferred from this document).", styles["BodyTight"]), Paragraph("Conclusion", styles["Subsection"]), Paragraph("This submission provides a reproducible comparative implementation and preserves the distinction between measurements and projections. Interpret results alongside successful-run counts and execution environment; incomplete service runs should be resolved and repeated before drawing comparative conclusions.", styles["BodyTight"])]
    for index, item in enumerate(story):
        if isinstance(item, Paragraph):
            text = item.getPlainText()
            if "[DOCKERHUB_USERNAME]" in text:
                push_note = next((note for note in data.get("notes", []) if note.startswith("Docker Hub push verified:")), None)
                status = html.escape(push_note) if push_note else "Publication was not verified in this run."
                story[index] = Paragraph(f"Docker Hub repository URL: https://hub.docker.com/r/raja6303/mongodb-exercise18. {status}", styles["BodyTight"])
            elif text.startswith("Submission note:"):
                note = text.replace("results/benchmark_results.json", results_path.as_posix())
                story[index] = Paragraph(note, styles["Small"])
    attempt_notes = [note for note in data.get("notes", []) if note.startswith("Full 100K attempt:")]
    if attempt_notes:
        story.extend([Paragraph("Execution Notes", styles["Section"])])
        story.extend(Paragraph(note, styles["BodyTight"]) for note in attempt_notes)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return destination


if __name__ == "__main__":
    print(build_report())
