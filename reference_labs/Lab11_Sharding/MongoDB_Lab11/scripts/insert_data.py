import os
import random
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "lab11")
COUNT = int(os.getenv("DOC_COUNT", "10000"))
BATCH_SIZE = 1000

client = MongoClient(URI, serverSelectionTimeoutMS=15000)
client.admin.command("ping")
db = client[DB_NAME]
hotspot = db["hotspot_data"]
even = db["even_data"]

# Start from a clean state when re-running the experiment.
hotspot.delete_many({})
even.delete_many({})

base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
rng = random.Random(11)

hotspot_docs = []
even_docs = []

for i in range(COUNT):
    # Strictly increasing timestamps create an ascending-key insert pattern.
    hotspot_docs.append({
        "_id": ObjectId(),
        "ts": base_time + timedelta(seconds=i),
        "order_no": i + 1,
        "amount": round(rng.uniform(10, 500), 2),
    })

    # Unique ObjectIds provide many hashed-key values.
    even_docs.append({
        "_id": ObjectId(),
        "user_id": ObjectId(),
        "order_no": i + 1,
        "amount": round(rng.uniform(10, 500), 2),
    })

for start in range(0, COUNT, BATCH_SIZE):
    hotspot.insert_many(hotspot_docs[start:start + BATCH_SIZE], ordered=False)
    even.insert_many(even_docs[start:start + BATCH_SIZE], ordered=False)
    print(f"Inserted {min(start + BATCH_SIZE, COUNT)} of {COUNT} into each collection")

print("\nInsertion complete.")
print("hotspot_data count:", hotspot.count_documents({}))
print("even_data count:", even.count_documents({}))
client.close()
