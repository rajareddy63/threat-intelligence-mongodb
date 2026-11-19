"""Ten-run, repeatable query and batch-insert benchmark harness."""
from __future__ import annotations

import statistics
import time
import uuid
from datetime import datetime, timedelta, timezone


def run_benchmarks(stores: dict, probe: dict, runs: int = 10, insert_batch_size: int = 50) -> dict:
    day_start = probe["observed_at"].replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    queries = {
        "threat_history": lambda store: store.threat_history(probe["indicator"]),
        "target_and_spread": lambda store: store.target_spread(probe["target"]),
        "daily_volume": lambda store: store.daily_volume(day_start, day_end),
    }
    result = {name: {"queries": {}, "insert_runs": [], "errors": []} for name in stores}
    for name, store in stores.items():
        for query_name, operation in queries.items():
            latencies = []
            errors = []
            for run in range(runs):
                started = time.perf_counter()
                try:
                    operation(store)
                    latencies.append(round((time.perf_counter() - started) * 1000, 3))
                except Exception as exc:
                    errors.append(f"run {run + 1}: {type(exc).__name__}: {exc}")
                    break
            result[name]["queries"][query_name] = {
                "latency_ms": latencies,
                "median_latency_ms": round(statistics.median(latencies), 3) if latencies else None,
                "successful_runs": len(latencies),
                "errors": errors,
            }
        for run in range(runs):
            batch = []
            now = datetime.now(timezone.utc)
            for _ in range(insert_batch_size):
                row = dict(probe)
                row["threat_id"] = str(uuid.uuid4())
                row["observed_at"] = now
                row["first_seen"] = now
                batch.append(row)
            started = time.perf_counter()
            try:
                store.bulk_insert(batch, batch_size=insert_batch_size)
                elapsed = time.perf_counter() - started
                result[name]["insert_runs"].append({
                    "records": insert_batch_size,
                    "elapsed_seconds": round(elapsed, 6),
                    "throughput_records_per_second": round(insert_batch_size / elapsed, 2) if elapsed else None,
                })
            except Exception as exc:
                result[name]["errors"].append(f"insert run {run + 1}: {type(exc).__name__}: {exc}")
                break
        throughputs = [row["throughput_records_per_second"] for row in result[name]["insert_runs"]]
        result[name]["median_insert_throughput_records_per_second"] = round(statistics.median(throughputs), 2) if throughputs else None
        result[name]["successful_insert_runs"] = len(throughputs)
    return {"runs_requested": runs, "insert_batch_size": insert_batch_size, "databases": result}
