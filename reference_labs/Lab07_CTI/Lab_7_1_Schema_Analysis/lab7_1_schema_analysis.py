"""
Lab 7.1: Analyze a Production Schema ($bsonSize, Indexing, Embedding vs Referencing)
"""
import json
import os
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = MongoClient(MONGO_URI)["cti_digest_prod"]

def run_lab_7_1():
    for col in ["sources", "actors", "threats"]:
        db[col].drop()

    with open(os.path.join(os.path.dirname(__file__), "cti_digest_dump.json")) as f:
        dump = json.load(f)

    db.sources.insert_many(dump["sources"])
    db.actors.insert_many(dump["actors"])
    db.threats.insert_many(dump["threats"])

    # Chapter 7 Indexes
    db.threats.create_index([("title", TEXT), ("summary", TEXT), ("cves", TEXT)], name="idx_threat_text")
    db.threats.create_index([("classification", ASCENDING), ("severity", DESCENDING)], name="idx_class_sev")
    db.threats.create_index([("source_id", ASCENDING)], name="idx_source_ref")
    db.threats.create_index([("actor_id", ASCENDING)], name="idx_actor_ref")
    db.threats.create_index([("iocs.value", ASCENDING)], name="idx_ioc_lookup")

    # $bsonSize Aggregation
    stats = list(db.threats.aggregate([
        {"$project": {"_id": 1, "title": 1, "bson_bytes": {"$bsonSize": "$$ROOT"}}},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "avg_bytes": {"$avg": "$bson_bytes"},
            "max_bytes": {"$max": "$bson_bytes"}
        }}
    ]))[0]

    limit_16mb = 16 * 1024 * 1024
    print(f"Docs Analyzed: {stats['count']}")
    print(f"Average BSON Size: {stats['avg_bytes']:.2f} bytes")
    print(f"Max BSON Size: {stats['max_bytes']} bytes ({(stats['max_bytes']/limit_16mb)*100:.6f}% of 16MB limit)")

if __name__ == "__main__":
    run_lab_7_1()
