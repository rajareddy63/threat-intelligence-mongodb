"""MongoDB schema, bulk loader, query and insert operations."""
from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, MongoClient, ReplaceOne


class MongoStore:
    def __init__(self, uri: str, database: str = "threatintel") -> None:
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, maxPoolSize=50)
        self.client.admin.command("ping")
        self.collection = self.client[database]["threats"]

    def initialize(self) -> None:
        self.collection.create_index([("indicator", ASCENDING), ("observed_at", DESCENDING)], name="indicator_history")
        self.collection.create_index([("target", ASCENDING), ("observed_at", DESCENDING)], name="target_spread")
        self.collection.create_index([("observed_at", ASCENDING), ("source", ASCENDING)], name="daily_volume")
        self.collection.create_index("threat_id", unique=True, name="threat_id_unique")
        self.collection.create_index("run_id", name="load_run_id")

    def bulk_insert(self, records: list[dict], batch_size: int = 2000) -> int:
        inserted = 0
        for offset in range(0, len(records), batch_size):
            batch = [dict(record) for record in records[offset:offset + batch_size]]
            operations = [ReplaceOne({"threat_id": record["threat_id"]}, record, upsert=True) for record in batch]
            self.collection.bulk_write(operations, ordered=False)
            inserted += len(batch)
        return inserted

    def count_records(self, run_id: str) -> int:
        return self.collection.count_documents({"run_id": run_id})

    def threat_history(self, indicator: str) -> list[dict]:
        return list(self.collection.find({"indicator": indicator}, {"_id": 0}).sort("observed_at", DESCENDING).limit(100))

    def target_spread(self, target: str) -> list[dict]:
        return list(self.collection.aggregate([
            {"$match": {"target": target}},
            {"$group": {"_id": "$source", "events": {"$sum": 1}, "spread": {"$sum": "$spread_count"}}},
            {"$sort": {"events": -1}},
        ]))

    def daily_volume(self, day_start, day_end) -> list[dict]:
        return list(self.collection.aggregate([
            {"$match": {"observed_at": {"$gte": day_start, "$lt": day_end}}},
            {"$group": {"_id": "$source", "events": {"$sum": 1}}},
        ]))

    def insert_one(self, record: dict) -> None:
        self.collection.insert_one(record)

    def close(self) -> None:
        self.client.close()
