"""Initialize stores, load a shared dataset, benchmark, and write result artifacts."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import platform
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from benchmark import run_benchmarks
from cassandra_operations import CassandraStore
from generate_threats import generate_threats
from mongo_operations import MongoStore
from neo4j_operations import Neo4jStore

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("exercise18")


def verified_benchmark_stores(stores: dict, status: dict, expected_records: int) -> dict:
    return {
        name: store for name, store in stores.items()
        if status.get(name, {}).get("loaded_records") == expected_records
        and status.get(name, {}).get("load_error") is None
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=100_000)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=18)
    parser.add_argument("--insert-batch-size", type=int, default=50)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    if args.records < 1 or args.runs < 1 or args.insert_batch_size < 1:
        parser.error("records, runs, and insert-batch-size must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex
    records = list(generate_threats(args.records, seed=args.seed))
    for record in records:
        record["run_id"] = run_id
    probe = records[0]
    configs = (
        ("mongodb", lambda: MongoStore(os.getenv("MONGO_URI", "mongodb://localhost:27017"))),
        ("cassandra", lambda: CassandraStore(os.getenv("CASSANDRA_HOSTS", "localhost").split(","), port=int(os.getenv("CASSANDRA_PORT", "9042")))),
        ("neo4j", lambda: Neo4jStore(os.getenv("NEO4J_URI", "bolt://localhost:7687"), os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "exercise18password"))),
    )
    stores, status, load_summary = {}, {}, {}
    for name, factory in configs:
        try:
            store = factory()
            store.initialize()
            stores[name] = store
            status[name] = {"connected": True, "loaded_records": 0, "load_state": "pending", "load_error": None}
            LOG.info("Connected and initialized %s", name)
        except Exception as exc:
            status[name] = {"connected": False, "loaded_records": 0, "load_error": f"{type(exc).__name__}: {exc}"}
            LOG.exception("Unable to initialize %s", name)
    for name, store in stores.items():
        begin = time.perf_counter()
        status[name]["load_state"] = "loading"
        written = 0
        try:
            written = store.bulk_insert(records)
        except Exception as exc:
            status[name]["load_error"] = f"{type(exc).__name__}: {exc}"
            LOG.exception("Bulk load failed for %s", name)
        try:
            confirmed = store.count_records(run_id)
            status[name]["loaded_records"] = confirmed
            if confirmed != args.records:
                mismatch = f"verified {confirmed} of {args.records} records for run {run_id}"
                status[name]["load_error"] = f"{status[name]['load_error']}; {mismatch}" if status[name]["load_error"] else mismatch
            status[name]["load_state"] = "complete" if confirmed == args.records else "incomplete"
        except Exception as exc:
            status[name]["load_state"] = "unverified"
            count_error = f"count verification failed: {type(exc).__name__}: {exc}"
            status[name]["load_error"] = f"{status[name]['load_error']}; {count_error}" if status[name]["load_error"] else count_error
            LOG.exception("Could not verify loaded record count for %s", name)
        elapsed = time.perf_counter() - begin
        load_summary[name] = {"attempted_records": args.records, "written_records_reported": written, "confirmed_records": status[name]["loaded_records"], "elapsed_seconds": round(elapsed, 3), "throughput_records_per_second": round(written / elapsed, 2) if elapsed and written else None}
        LOG.info("Verified %s of %s records in %s", status[name]["loaded_records"], args.records, name)

    benchmark_stores = verified_benchmark_stores(stores, status, args.records)
    skipped_databases = {
        name: status.get(name, {}).get("load_error") or "not connected; dataset not verified"
        for name in ("mongodb", "cassandra", "neo4j") if name not in benchmark_stores
    }
    benchmark = run_benchmarks(benchmark_stores, probe, args.runs, args.insert_batch_size)
    benchmark["skipped_databases"] = skipped_databases
    result = {
        "project": "Exercise 18 - Comparative Capstone",
        "dataset_records_requested": args.records,
        "seed": args.seed,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor() or "not reported", "logical_cpus": os.cpu_count(), "docker_image": os.getenv("HOSTNAME", "local process")},
        "database_status": status,
        "bulk_load": load_summary,
        "benchmark": benchmark,
        "notes": ["Query benchmarks run only for databases with an exact verified count matching the requested dataset.", "Insert benchmark rate is measured using repeated batches of the configured size; it is not a single-row latency estimate."],
    }
    json_path = args.output_dir / "benchmark_results.json"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, default=str)
    csv_path = args.output_dir / "benchmark_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("database", "workload", "median_latency_ms", "median_insert_throughput_records_per_second", "successful_runs", "requested_runs", "dataset_records", "status"))
        for name in ("mongodb", "cassandra", "neo4j"):
            db = benchmark["databases"].get(name, {})
            db_status = status.get(name, {})
            load_complete = db_status.get("loaded_records") == args.records and not db_status.get("load_error")
            for query in ("threat_history", "target_and_spread", "daily_volume"):
                stats = db.get("queries", {}).get(query, {})
                query_value = stats.get("median_latency_ms")
                query_status = "measured; complete load" if query_value is not None and load_complete else benchmark["skipped_databases"].get(name, "unavailable")
                writer.writerow((name, query, query_value, "", stats.get("successful_runs", 0), args.runs, args.records, query_status))
            insert_value = db.get("median_insert_throughput_records_per_second")
            insert_status = "measured; complete load" if insert_value is not None and load_complete else benchmark["skipped_databases"].get(name, "unavailable")
            writer.writerow((name, "insert_throughput", "", insert_value, db.get("successful_insert_runs", 0), args.runs, args.records, insert_status))
    for store in stores.values():
        try:
            store.close()
        except Exception:
            LOG.exception("Error closing database connection")
    LOG.info("Wrote %s and %s", json_path, csv_path)
    try:
        from generate_report import build_report
        build_report(json_path, args.output_dir)
    except Exception:
        LOG.exception("PDF generation failed; raw results remain available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
