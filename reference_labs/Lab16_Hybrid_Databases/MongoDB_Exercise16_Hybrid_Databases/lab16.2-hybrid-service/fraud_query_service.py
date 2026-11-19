from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import (
    CASSANDRA_CONTACT_POINTS,
    CASSANDRA_KEYSPACE,
    MONGO_COLLECTION,
    MONGO_DB,
    MONGO_URI,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
)

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
except Exception:  # pragma: no cover
    MongoClient = None

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover
    GraphDatabase = None


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    reset_timeout_seconds: int = 30
    consecutive_failures: int = 0
    open_until: float = 0.0

    def allow_request(self) -> bool:
        if self.consecutive_failures >= self.failure_threshold:
            if time.time() < self.open_until:
                return False
            self.consecutive_failures = 0
        return True

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.open_until = 0.0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.open_until = time.time() + self.reset_timeout_seconds


class FraudQueryService:
    def __init__(
        self,
        mongo_uri: str = MONGO_URI,
        mongo_db: str = MONGO_DB,
        mongo_collection: str = MONGO_COLLECTION,
        cassandra_contact_points: Optional[List[str]] = None,
        cassandra_keyspace: str = CASSANDRA_KEYSPACE,
        neo4j_uri: str = NEO4J_URI,
        neo4j_user: str = NEO4J_USER,
        neo4j_password: str = NEO4J_PASSWORD,
    ):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.cassandra_contact_points = cassandra_contact_points or CASSANDRA_CONTACT_POINTS
        self.cassandra_keyspace = cassandra_keyspace
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        self.mongo_client = self._connect_mongo() if MongoClient else None
        self.cassandra_session = self._connect_cassandra()
        self.neo4j_driver = self._connect_neo4j() if GraphDatabase else None
        self.breakers = {
            "mongo": CircuitBreaker("mongo"),
            "cassandra": CircuitBreaker("cassandra"),
            "neo4j": CircuitBreaker("neo4j"),
        }
        self._seed_demo_data()

    def close(self):
        if hasattr(self, "neo4j_driver") and self.neo4j_driver is not None:
            self.neo4j_driver.close()
            self.neo4j_driver = None
        if hasattr(self, "mongo_client") and self.mongo_client is not None:
            self.mongo_client.close()
        if hasattr(self, "cassandra_session") and self.cassandra_session is not None:
            self.cassandra_session.shutdown()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _connect_mongo(self):
        try:
            client = MongoClient(self.mongo_uri, maxPoolSize=10, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            return client
        except Exception:
            logger.warning("MongoDB unavailable; continuing in degraded mode.")
            return None

    def _connect_cassandra(self):
        try:
            try:
                import eventlet
                eventlet.monkey_patch()
            except Exception:
                pass

            from cassandra.cluster import Cluster
            try:
                from cassandra.io.eventletreactor import EventletConnection
            except Exception:  # pragma: no cover
                EventletConnection = None

            kwargs = {"contact_points": self.cassandra_contact_points, "connect_timeout": 10}
            if EventletConnection is not None:
                kwargs["connection_class"] = EventletConnection
            cluster = Cluster(**kwargs)
            session = cluster.connect()
            session.execute(
                f"CREATE KEYSPACE IF NOT EXISTS {self.cassandra_keyspace} WITH REPLICATION = {{ 'class' : 'SimpleStrategy', 'replication_factor' : 1 }}"
            )
            session.set_keyspace(self.cassandra_keyspace)
            session.execute(
                "CREATE TABLE IF NOT EXISTS user_profiles (user_id text, event_time bigint, event_type text, amount double, merchant text, details text, PRIMARY KEY (user_id, event_time)) WITH CLUSTERING ORDER BY (event_time DESC)"
            )
            return session
        except Exception:
            logger.warning("Cassandra unavailable; continuing in degraded mode.")
            return None

    def _connect_neo4j(self):
        try:
            if GraphDatabase is None:
                return None
            return GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
                max_connection_pool_size=10,
            )
        except Exception:
            logger.warning("Neo4j unavailable; continuing in degraded mode.")
            return None

    def _seed_demo_data(self):
        if self.mongo_client is not None and hasattr(self.mongo_client, "__getitem__"):
            db = self.mongo_client[self.mongo_db]
            collection = db[self.mongo_collection]
            collection.update_one(
                {"txn_id": "TXN-1001"},
                {"$set": {
                    "txn_id": "TXN-1001",
                    "user_id": "U-1001",
                    "amount": 1450.75,
                    "merchant": "Sample Merchant",
                    "timestamp": "2026-11-15T10:00:00Z",
                    "risk_score": 0.84,
                }},
                upsert=True,
            )

        if self.cassandra_session is not None and hasattr(self.cassandra_session, "execute"):
            self.cassandra_session.execute(
                "INSERT INTO user_profiles (user_id, event_time, event_type, amount, merchant, details) VALUES (%s, %s, %s, %s, %s, %s)",
                ("U-1001", 1760000000000, "transfer", 1450.75, "Sample Merchant", "initial transfer"),
            )
            self.cassandra_session.execute(
                "INSERT INTO user_profiles (user_id, event_time, event_type, amount, merchant, details) VALUES (%s, %s, %s, %s, %s, %s)",
                ("U-1001", 1760000001000, "login", 0.0, "portal", "successful login"),
            )

        if self.neo4j_driver is not None and hasattr(self.neo4j_driver, "session"):
            try:
                with self.neo4j_driver.session(database="neo4j") as session:
                    session.run(
                        """
                        MERGE (u1:User {user_id: 'U-1001'})
                        MERGE (u2:User {user_id: 'U-1002'})
                        MERGE (u3:User {user_id: 'U-1003'})
                        MERGE (u4:User {user_id: 'U-1004'})
                        MERGE (u1)-[:TRANSFERRED_TO]->(u2)
                        MERGE (u2)-[:TRANSFERRED_TO]->(u3)
                        MERGE (u1)-[:TRANSFERRED_TO]->(u4)
                        """
                    )
            except Exception:
                pass

    def _db_unavailable(self, database: str, reason: str) -> Dict[str, Any]:
        self.breakers[database].record_failure()
        return {"status": "unavailable", "database": database, "reason": reason}

    def get_transaction(self, txn_id: str) -> Dict[str, Any]:
        breaker = self.breakers["mongo"]
        if not breaker.allow_request():
            return {"status": "unavailable", "database": "mongo", "reason": "circuit breaker open"}
        if self.mongo_client is None:
            return self._db_unavailable("mongo", "MongoDB connection unavailable")
        try:
            result = self.mongo_client[self.mongo_db][self.mongo_collection].find_one({"txn_id": txn_id}, {"_id": 0})
            if not result:
                breaker.record_success()
                return {"status": "not_found", "database": "mongo", "txn_id": txn_id}
            breaker.record_success()
            return result
        except Exception as exc:
            logger.exception("Mongo transaction lookup failed")
            return self._db_unavailable("mongo", str(exc))

    def get_user_profile(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        breaker = self.breakers["cassandra"]
        if not breaker.allow_request():
            return {"status": "unavailable", "database": "cassandra", "reason": "circuit breaker open"}
        if self.cassandra_session is None:
            return self._db_unavailable("cassandra", "Cassandra connection unavailable")
        try:
            query = "SELECT user_id, event_time, event_type, amount, merchant, details FROM user_profiles WHERE user_id = %s LIMIT %s"
            rows = self.cassandra_session.execute(query, (user_id, limit))
            events = [
                {
                    "user_id": row.user_id,
                    "event_time": row.event_time,
                    "event_type": row.event_type,
                    "amount": row.amount,
                    "merchant": row.merchant,
                    "details": row.details,
                }
                for row in rows
            ]
            breaker.record_success()
            return {"status": "ok", "database": "cassandra", "user_id": user_id, "events": events}
        except Exception as exc:
            logger.exception("Cassandra profile lookup failed")
            return self._db_unavailable("cassandra", str(exc))

    def detect_fraud_rings(self, user_id: str, max_hops: int = 3) -> Dict[str, Any]:
        breaker = self.breakers["neo4j"]
        if not breaker.allow_request():
            return {"status": "unavailable", "database": "neo4j", "reason": "circuit breaker open"}
        if self.neo4j_driver is None:
            return self._db_unavailable("neo4j", "Neo4j connection unavailable")
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                query = """
                MATCH p=(u:User {user_id: $user_id})-[:TRANSFERRED_TO*1..10]-(other:User)
                WHERE other.user_id <> $user_id AND length(p) <= $max_hops
                RETURN DISTINCT other.user_id AS user_id, length(p) AS hops, [n IN nodes(p) | n.user_id] AS path
                ORDER BY hops ASC
                LIMIT 50
                """
                rows = session.run(query, parameters={"user_id": user_id, "max_hops": max_hops})
                related_accounts = [dict(record) for record in rows]
            breaker.record_success()
            return {"status": "ok", "database": "neo4j", "user_id": user_id, "related_accounts": related_accounts}
        except Exception as exc:
            logger.exception("Neo4j fraud ring lookup failed")
            return self._db_unavailable("neo4j", str(exc))

    def analyze_fraud(self, txn_id: str, user_id: Optional[str] = None, max_hops: int = 3) -> Dict[str, Any]:
        transaction = self.get_transaction(txn_id)
        if user_id is None and isinstance(transaction, dict):
            user_id = transaction.get("user_id")
        if not user_id:
            user_id = "UNKNOWN_USER"

        profile = self.get_user_profile(user_id)
        rings = self.detect_fraud_rings(user_id, max_hops=max_hops)

        response = {
            "transaction": transaction,
            "user_profile": profile,
            "fraud_rings": rings,
            "summary": {
                "transaction_id": txn_id,
                "user_id": user_id,
                "risk_score": transaction.get("risk_score", 0) if isinstance(transaction, dict) else 0,
                "related_account_count": len(rings.get("related_accounts", [])) if isinstance(rings, dict) else 0,
            },
        }
        return response
