"""Neo4j property-graph schema, batch loader and query operations."""
from __future__ import annotations

from neo4j import GraphDatabase


class Neo4jStore:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=15, max_transaction_retry_time=300, max_connection_pool_size=10)
        self.driver.verify_connectivity()

    def initialize(self) -> None:
        statements = (
            "CREATE CONSTRAINT threat_id IF NOT EXISTS FOR (t:Threat) REQUIRE t.threat_id IS UNIQUE",
            "CREATE INDEX threat_indicator IF NOT EXISTS FOR (t:Threat) ON (t.indicator)",
            "CREATE INDEX threat_target IF NOT EXISTS FOR (t:Threat) ON (t.target)",
            "CREATE INDEX threat_observed IF NOT EXISTS FOR (t:Threat) ON (t.observed_at)",
            "CREATE INDEX threat_load_run IF NOT EXISTS FOR (t:Threat) ON (t.run_id)",
        )
        with self.driver.session() as session:
            for statement in statements:
                session.run(statement).consume()

    @staticmethod
    def _properties(record: dict) -> dict:
        return {**record, "observed_at": record["observed_at"].isoformat(), "first_seen": record["first_seen"].isoformat()}

    def bulk_insert(self, records: list[dict], batch_size: int = 250) -> int:
        query = """
        UNWIND $rows AS row
        MERGE (t:Threat {threat_id: row.threat_id}) SET t = row
        MERGE (target:Target {name: row.target})
        MERGE (t)-[:TARGETS]->(target)
        """
        with self.driver.session() as session:
            for offset in range(0, len(records), batch_size):
                rows = [self._properties(row) for row in records[offset:offset + batch_size]]
                session.execute_write(lambda tx, payload: tx.run(query, rows=payload).consume(), rows)
        return len(records)

    def count_records(self, run_id: str) -> int:
        with self.driver.session() as session:
            result = session.run("MATCH (t:Threat {run_id: $run_id}) RETURN count(t) AS record_count", run_id=run_id)
            record = result.single()
            return record["record_count"] if record else 0

    def threat_history(self, indicator: str):
        with self.driver.session() as session:
            return session.execute_read(lambda tx: tx.run("MATCH (t:Threat {indicator: $indicator}) RETURN t.threat_id AS id, t.observed_at AS observed_at, t.severity AS severity ORDER BY t.observed_at DESC LIMIT 100", indicator=indicator).data())

    def target_spread(self, target: str):
        with self.driver.session() as session:
            return session.execute_read(lambda tx: tx.run("MATCH (t:Threat)-[:TARGETS]->(:Target {name: $target}) RETURN t.source AS source, count(t) AS events, sum(t.spread_count) AS spread ORDER BY events DESC", target=target).data())

    def daily_volume(self, day_start: str, day_end: str):
        if hasattr(day_start, "isoformat"):
            day_start, day_end = day_start.isoformat(), day_end.isoformat()
        with self.driver.session() as session:
            return session.execute_read(lambda tx: tx.run("MATCH (t:Threat) WHERE t.observed_at >= $start AND t.observed_at < $end RETURN t.source AS source, count(t) AS events", start=day_start, end=day_end).data())

    def insert_one(self, record: dict) -> None:
        query = "MERGE (t:Threat {threat_id: $row.threat_id}) SET t = $row MERGE (target:Target {name: $row.target}) MERGE (t)-[:TARGETS]->(target)"
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run(query, row=self._properties(record)).consume())

    def close(self) -> None:
        self.driver.close()
