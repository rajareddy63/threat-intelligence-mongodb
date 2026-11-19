"""Cassandra denormalized tables and workload operations."""
from __future__ import annotations

import time

from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args

KEYSPACE = "threatintel"


class CassandraStore:
    def __init__(self, hosts: list[str], port: int = 9042) -> None:
        self.cluster = Cluster(hosts, port=port, connect_timeout=8)
        self.session = self.cluster.connect()
        self.session.default_timeout = 180
        self.session.execute(f"CREATE KEYSPACE IF NOT EXISTS {KEYSPACE} WITH replication = {{'class':'SimpleStrategy','replication_factor':1}}")
        self.session.set_keyspace(KEYSPACE)
        self._statements = None

    def initialize(self) -> None:
        self.session.execute("CREATE TABLE IF NOT EXISTS history_by_indicator (indicator text, observed_at timestamp, threat_id text, source text, severity text, target text, spread_count int, PRIMARY KEY (indicator, observed_at, threat_id)) WITH CLUSTERING ORDER BY (observed_at DESC)")
        self.session.execute("CREATE TABLE IF NOT EXISTS target_spread_by_target (target text, observed_at timestamp, threat_id text, source text, severity text, spread_count int, PRIMARY KEY (target, observed_at, threat_id)) WITH CLUSTERING ORDER BY (observed_at DESC)")
        self.session.execute("CREATE TABLE IF NOT EXISTS daily_volume_by_day (day date, source text, observed_at timestamp, threat_id text, PRIMARY KEY (day, source, observed_at, threat_id))")
        self.session.execute("CREATE TABLE IF NOT EXISTS loaded_threats_by_run (run_id text, threat_id text, PRIMARY KEY (run_id, threat_id))")
        self._statements = (
            self.session.prepare("INSERT INTO history_by_indicator (indicator, observed_at, threat_id, source, severity, target, spread_count) VALUES (?, ?, ?, ?, ?, ?, ?)"),
            self.session.prepare("INSERT INTO target_spread_by_target (target, observed_at, threat_id, source, severity, spread_count) VALUES (?, ?, ?, ?, ?, ?)"),
            self.session.prepare("INSERT INTO daily_volume_by_day (day, source, observed_at, threat_id) VALUES (?, ?, ?, ?)"),
            self.session.prepare("INSERT INTO loaded_threats_by_run (run_id, threat_id) VALUES (?, ?)"),
        )

    @staticmethod
    def _time(record):
        return record["observed_at"].replace(tzinfo=None)

    def bulk_insert(self, records: list[dict], batch_size: int = 500) -> int:
        if self._statements is None:
            self.initialize()
        statements = self._statements
        inserted = 0
        for offset in range(0, len(records), batch_size):
            chunk = records[offset:offset + batch_size]
            history = [(r["indicator"], self._time(r), r["threat_id"], r["source"], r["severity"], r["target"], r["spread_count"]) for r in chunk]
            target = [(r["target"], self._time(r), r["threat_id"], r["source"], r["severity"], r["spread_count"]) for r in chunk]
            daily = [(r["observed_at"].date(), r["source"], self._time(r), r["threat_id"]) for r in chunk]
            manifest = [(r["run_id"], r["threat_id"]) for r in chunk]
            for statement, params in zip(statements, (history, target, daily, manifest)):
                for attempt in range(3):
                    try:
                        outcomes = execute_concurrent_with_args(self.session, statement, params, concurrency=2, raise_on_first_error=True)
                        if any(not success for success, _ in outcomes):
                            raise RuntimeError("Cassandra reported a failed row write")
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        time.sleep(2 ** attempt)
            inserted += len(chunk)
        return inserted

    def count_records(self, run_id: str) -> int:
        row = self.session.execute("SELECT COUNT(*) AS record_count FROM loaded_threats_by_run WHERE run_id = %s", (run_id,), timeout=180).one()
        return row.record_count if row else 0

    def threat_history(self, indicator: str):
        return list(self.session.execute("SELECT threat_id, observed_at, severity, source FROM history_by_indicator WHERE indicator = %s LIMIT 100", (indicator,)))

    def target_spread(self, target: str):
        rows = self.session.execute("SELECT source, spread_count FROM target_spread_by_target WHERE target = %s", (target,))
        summary = {}
        for row in rows:
            item = summary.setdefault(row.source, {"events": 0, "spread": 0})
            item["events"] += 1
            item["spread"] += row.spread_count
        return summary

    def daily_volume(self, day_start, day_end=None):
        day = day_start.date() if hasattr(day_start, "date") else day_start
        rows = self.session.execute("SELECT source, threat_id FROM daily_volume_by_day WHERE day = %s", (day,))
        summary = {}
        for row in rows:
            summary[row.source] = summary.get(row.source, 0) + 1
        return summary

    def insert_one(self, record: dict) -> None:
        if self._statements is None:
            self.initialize()
        moment = self._time(record)
        args = (
            (record["indicator"], moment, record["threat_id"], record["source"], record["severity"], record["target"], record["spread_count"]),
            (record["target"], moment, record["threat_id"], record["source"], record["severity"], record["spread_count"]),
            (record["observed_at"].date(), record["source"], moment, record["threat_id"]),
        )
        for statement, values in zip(self._statements, args):
            self.session.execute(statement, values)

    def close(self) -> None:
        self.cluster.shutdown()
