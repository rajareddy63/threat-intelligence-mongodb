from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from pymongo import MongoClient
from pymongo.errors import PyMongoError


LOG = logging.getLogger("lab14")
POLL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "30"))
CACHE_WARNING_PERCENT = float(os.getenv("CACHE_WARNING_PERCENT", "80"))
REPLICATION_LAG_WARNING_SECONDS = float(
    os.getenv("REPLICATION_LAG_WARNING_SECONDS", "10")
)
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
MONGO_URI = os.getenv("MONGODB_URI") or (
    "mongodb://"
    f"{quote_plus(os.getenv('MONGO_INITDB_ROOT_USERNAME', 'admin'))}:"
    f"{quote_plus(os.getenv('MONGO_INITDB_ROOT_PASSWORD', 'ChangeMe!123'))}"
    "@mongo1:27017/?authSource=admin&replicaSet=rs0&readPreference=primaryPreferred"
)
DB_NAME = os.getenv("APP_DATABASE", "lab14")
COLLECTION_NAME = os.getenv("APP_COLLECTION", "orders")
LOG_PATH = os.getenv("MONITOR_LOG_PATH", "/logs/monitor.jsonl")
RESULTS_PATH = os.getenv("BENCHMARK_RESULTS_PATH", "/results/benchmark.json")

_state_lock = threading.Lock()
_latest_metrics: dict[str, Any] | None = None
_last_error: str | None = None
_stop_event = threading.Event()
_alert_last_sent: dict[str, float] = {}


def build_client() -> MongoClient:
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)


def _member_lag_seconds(primary: dict[str, Any], member: dict[str, Any]) -> float | None:
    primary_time = primary.get("optimeDate") or primary.get("lastAppliedWallTime")
    member_time = member.get("optimeDate") or member.get("lastAppliedWallTime")
    if primary_time is not None and member_time is not None:
        return max(0.0, (primary_time - member_time).total_seconds())

    primary_optime = primary.get("optime")
    member_optime = member.get("optime")
    if primary_optime is not None and member_optime is not None:
        return max(0.0, primary_optime["ts"].as_datetime().timestamp()
                   - member_optime["ts"].as_datetime().timestamp())
    return None


def collect_metrics(client: MongoClient | None = None) -> dict[str, Any]:
    owns_client = client is None
    active_client = client or build_client()
    try:
        server = active_client.admin.command("serverStatus")
        replica = active_client.admin.command("replSetGetStatus")
        connections = server.get("connections", {})
        wired_tiger = server.get("wiredTiger", {}).get("cache", {})
        cache_used = int(wired_tiger.get("bytes currently in the cache", 0))
        cache_maximum = int(wired_tiger.get("maximum bytes configured", 0))
        cache_percent = (cache_used * 100.0 / cache_maximum) if cache_maximum else 0.0
        members = replica.get("members", [])
        primary = next(
            (member for member in members if member.get("stateStr") == "PRIMARY"),
            None,
        )
        secondary_lags = [
            {
                "name": member.get("name"),
                "seconds": _member_lag_seconds(primary, member),
            }
            for member in members
            if member.get("stateStr") == "SECONDARY" and primary
        ]
        measured_at = datetime.now(timezone.utc).isoformat()
        return {
            "timestamp": measured_at,
            "connections": {
                "current": int(connections.get("current", 0)),
                "available": int(connections.get("available", 0)),
            },
            "opcounters": server.get("opcounters", {}),
            "wiredTigerCache": {
                "usedBytes": cache_used,
                "maximumBytes": cache_maximum,
                "usedPercent": round(cache_percent, 2),
            },
            "replicaSet": {
                "name": replica.get("set"),
                "myState": replica.get("myState"),
                "primary": primary.get("name") if primary else None,
                "members": [
                    {
                        "name": member.get("name"),
                        "state": member.get("stateStr"),
                        "health": member.get("health"),
                    }
                    for member in members
                ],
                "secondaryLags": secondary_lags,
                "maximumLagSeconds": max(
                    (lag["seconds"] or 0 for lag in secondary_lags), default=0
                ),
            },
        }
    finally:
        if owns_client:
            active_client.close()


def _send_webhook(alert: dict[str, Any]) -> None:
    if not WEBHOOK_URL:
        return
    request = Request(
        WEBHOOK_URL,
        data=json.dumps(alert).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Webhook returned HTTP {response.status}")
    except (OSError, URLError, RuntimeError) as exc:
        LOG.error("Webhook delivery failed: %s", exc)
        raise


def evaluate_alerts(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    now = time.monotonic()
    alerts: list[dict[str, Any]] = []
    cache_percent = metrics["wiredTigerCache"]["usedPercent"]
    if cache_percent >= CACHE_WARNING_PERCENT:
        alerts.append(
            {
                "severity": "warning",
                "type": "wiredtiger_cache",
                "value": cache_percent,
                "threshold": CACHE_WARNING_PERCENT,
                "message": (
                    f"WiredTiger cache usage is {cache_percent:.2f}% "
                    f"(warning threshold {CACHE_WARNING_PERCENT:.2f}%)."
                ),
            }
        )
    lag_seconds = metrics["replicaSet"]["maximumLagSeconds"]
    if lag_seconds > REPLICATION_LAG_WARNING_SECONDS:
        alerts.append(
            {
                "severity": "warning",
                "type": "replication_lag",
                "value": lag_seconds,
                "threshold": REPLICATION_LAG_WARNING_SECONDS,
                "message": (
                    f"Maximum secondary replication lag is {lag_seconds:.2f}s "
                    f"(warning threshold {REPLICATION_LAG_WARNING_SECONDS:.2f}s)."
                ),
            }
        )

    for alert in alerts:
        key = alert["type"]
        if now - _alert_last_sent.get(key, 0) >= 300:
            alert["timestamp"] = metrics["timestamp"]
            LOG.warning("%s", json.dumps(alert))
            try:
                _send_webhook(alert)
            except (OSError, RuntimeError) as exc:
                LOG.error("Alert %s could not be delivered: %s", key, exc)
            else:
                _alert_last_sent[key] = now
    return alerts


def _append_log(entry: dict[str, Any]) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        LOG.exception("Could not write monitoring log to %s", LOG_PATH)


def _monitor_loop() -> None:
    global _latest_metrics, _last_error
    while not _stop_event.is_set():
        try:
            metrics = collect_metrics()
            alerts = evaluate_alerts(metrics)
            _append_log({"metrics": metrics, "alerts": alerts})
            with _state_lock:
                _latest_metrics = metrics
                _last_error = None
        except PyMongoError as exc:
            LOG.exception("MongoDB monitoring sample failed")
            with _state_lock:
                _last_error = str(exc)
            _append_log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                }
            )
        _stop_event.wait(POLL_SECONDS)


def _dashboard_html() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>MongoDB Production Monitor</title>
<style>
body{font:16px system-ui,sans-serif;background:#101820;color:#eef3f6;margin:0;padding:2rem}
main{max-width:1100px;margin:auto}h1{color:#00ed64;margin-bottom:.3rem}
.muted{color:#aab8c2}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem;margin:1.5rem 0}
section{background:#1d2b36;border-radius:12px;padding:1.2rem;box-shadow:0 4px 14px #0004}
.value{font-size:2rem;font-weight:700;color:#00ed64}pre{white-space:pre-wrap;overflow-wrap:anywhere}
.warn{color:#ffb74d}.ok{color:#00ed64}footer{margin-top:1rem}
</style></head><body><main>
<h1>MongoDB Production Monitor</h1><div class="muted">Live replica-set health and WiredTiger metrics · sampled every 30 seconds</div>
<div class="grid">
<section><h2>Connections</h2><div class="value" id="connections">Loading…</div><div id="available"></div></section>
<section><h2>WiredTiger cache</h2><div class="value" id="cache">Loading…</div><div id="cacheBytes"></div></section>
<section><h2>Replica set</h2><div class="value" id="primary">Loading…</div><pre id="members"></pre></section>
<section><h2>Opcounters</h2><pre id="opcounters">Loading…</pre></section>
<section><h2>Replication lag</h2><div class="value" id="lag">Loading…</div><pre id="lags"></pre></section>
</div><footer class="muted">Last sample: <span id="timestamp">never</span> · <span id="status">Connecting…</span></footer>
<script>
async function refresh(){try{const r=await fetch('/api/metrics',{cache:'no-store'});const d=await r.json();
if(!r.ok)throw new Error(d.error||r.statusText);const m=d.metrics;
document.getElementById('connections').textContent=m.connections.current;
document.getElementById('available').textContent=`${m.connections.available} available`;
const p=m.wiredTigerCache.usedPercent;const c=document.getElementById('cache');
c.textContent=`${p.toFixed(2)}%`;c.className='value '+(p>=80?'warn':'ok');
document.getElementById('cacheBytes').textContent=`${m.wiredTigerCache.usedBytes.toLocaleString()} / ${m.wiredTigerCache.maximumBytes.toLocaleString()} bytes`;
document.getElementById('primary').textContent=m.replicaSet.primary||'No primary';
document.getElementById('members').textContent=m.replicaSet.members.map(x=>`${x.name}: ${x.state}`).join('\\n');
document.getElementById('opcounters').textContent=JSON.stringify(m.opcounters,null,2);
const l=m.replicaSet.maximumLagSeconds,le=document.getElementById('lag');le.textContent=`${l.toFixed(2)}s`;le.className='value '+(l>10?'warn':'ok');
document.getElementById('lags').textContent=m.replicaSet.secondaryLags.map(x=>`${x.name}: ${x.seconds===null?'unknown':x.seconds.toFixed(2)+'s'}`).join('\\n');
document.getElementById('timestamp').textContent=m.timestamp;document.getElementById('status').textContent='Connected';
}catch(e){document.getElementById('status').textContent=`Error: ${e.message}`;document.getElementById('status').className='warn'}}
refresh();setInterval(refresh,30000);
</script></main></body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            body = _dashboard_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        elif self.path == "/api/metrics":
            with _state_lock:
                metrics, error = _latest_metrics, _last_error
            status = 200 if metrics is not None else 503
            body = json.dumps({"metrics": metrics, "error": error}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
        else:
            self.send_error(404)
            return
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args: Any) -> None:
        LOG.info("dashboard: " + _format, *args)


def run_dashboard() -> None:
    sampler = threading.Thread(target=_monitor_loop, daemon=True)
    sampler.start()
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    LOG.info("Dashboard listening on http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        _stop_event.set()
        sampler.join(timeout=5)


def run_smoke_test() -> dict[str, Any]:
    client = build_client()
    try:
        collection = client[DB_NAME][COLLECTION_NAME]
        payload = {
            "orderId": f"PO-{int(time.time() * 1000)}",
            "customer": "exercise-14",
            "status": "ready",
            "amount": 149.99,
            "createdAt": datetime.now(timezone.utc),
        }
        result = collection.insert_one(payload)
        document = collection.find_one({"_id": result.inserted_id})
        if document is None:
            raise RuntimeError("Inserted document could not be read back")
        return {"inserted_id": str(result.inserted_id), "document": document}
    finally:
        client.close()


def run_benchmarks(counts: list[int]) -> list[dict[str, Any]]:
    client = build_client()
    results: list[dict[str, Any]] = []
    try:
        for count in counts:
            if count <= 0:
                raise ValueError(f"Benchmark count must be positive: {count}")
            name = f"benchmark_{count}_{int(time.time())}"
            collection = client[DB_NAME][name]
            documents = [
                {
                    "sequence": index,
                    "payload": f"exercise-14-document-{index:06d}",
                    "active": True,
                    "value": index % 1000,
                }
                for index in range(count)
            ]
            started = time.perf_counter()
            collection.insert_many(documents, ordered=False)
            write_seconds = time.perf_counter() - started

            started = time.perf_counter()
            read_count = sum(1 for _ in collection.find({}, {"_id": 1}))
            read_seconds = time.perf_counter() - started
            result = {
                "documents": count,
                "writeSeconds": round(write_seconds, 4),
                "writeDocumentsPerSecond": round(count / write_seconds, 2),
                "readSeconds": round(read_seconds, 4),
                "readDocumentsPerSecond": round(read_count / read_seconds, 2),
                "verifiedDocuments": read_count,
                "collection": name,
            }
            if read_count != count:
                raise RuntimeError(f"Expected {count} documents, read {read_count}")
            results.append(result)
            collection.drop()
            print(json.dumps(result))
    finally:
        client.close()

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as result_file:
        json.dump(
            {
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "results": results,
            },
            result_file,
            indent=2,
        )
    print(f"Results saved to {RESULTS_PATH}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise 14 MongoDB tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("dashboard", help="Run the web dashboard and sampler")
    subparsers.add_parser("smoke-test", help="Insert and read back a test document")
    benchmark_parser = subparsers.add_parser("benchmark", help="Run insert/read benchmarks")
    benchmark_parser.add_argument(
        "--counts", nargs="+", type=int, default=[1000, 10000, 100000]
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.command == "dashboard":
        run_dashboard()
    elif args.command == "smoke-test":
        print(json.dumps(run_smoke_test(), default=str))
    elif args.command == "benchmark":
        run_benchmarks(args.counts)


if __name__ == "__main__":
    main()
