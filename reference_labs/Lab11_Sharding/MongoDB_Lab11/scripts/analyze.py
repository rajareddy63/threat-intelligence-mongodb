import json
import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient

URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "lab11")

client = MongoClient(URI, serverSelectionTimeoutMS=15000)
client.admin.command("ping")
db = client[DB_NAME]

def show_stats(collection_name):
    print(f"\n===== collStats: {collection_name} =====")
    result = db.command("collStats", collection_name)
    # The per-shard section is present when connected through mongos.
    print(json.dumps({
        "ns": result.get("ns"),
        "count": result.get("count"),
        "size": result.get("size"),
        "shards": result.get("shards", {}),
    }, indent=2, default=str))

show_stats("hotspot_data")
show_stats("even_data")

print("\n===== Timestamp range query explain =====")
ts_query = {
    "ts": {
        "$gte": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "$lt": datetime(2025, 1, 1, tzinfo=timezone.utc).replace(day=2),
    }
}
ts_explain = db.command({
    "explain": {
        "find": "hotspot_data",
        "filter": ts_query,
    },
    "verbosity": "queryPlanner",
})
print(json.dumps(ts_explain.get("queryPlanner", {}), indent=2, default=str))

print("\n===== Hashed user_id range query explain =====")
# ObjectId bounds are illustrative and intentionally cover a broad range.
hashed_query = {
    "user_id": {
        "$gte": ObjectId("000000000000000000000000"),
        "$lt": ObjectId("ffffffffffffffffffffffff"),
    }
}
hashed_explain = db.command({
    "explain": {
        "find": "even_data",
        "filter": hashed_query,
    },
    "verbosity": "queryPlanner",
})
print(json.dumps(hashed_explain.get("queryPlanner", {}), indent=2, default=str))

print("\n===== Shard status =====")
status = client.admin.command("listShards")
print(json.dumps(status, indent=2, default=str))

client.close()
