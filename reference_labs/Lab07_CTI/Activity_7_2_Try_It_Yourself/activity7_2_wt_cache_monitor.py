"""
Activity 7.2 (Try It Yourself): WiredTiger Cache Hit Ratio Monitor (Every 10s)
Browses for newer threat reports not yet in DB and logs cache metrics every 10 seconds.
"""
import os
import time
import random
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = MongoClient(MONGO_URI)["cti_digest_prod"]
col = db["annual_reports_workingset"]

def monitor_cache(cycles: int = 5):
    for step in range(1, cycles + 1):
        for _ in range(2000):
            idx = random.randint(0, 102_000)
            rid = f"RPT-2026-{idx:06d}"
            if col.find_one({"report_id": rid}) is None and idx >= 100_000:
                col.insert_one({"report_id": rid, "vendor": "CTI Live Feed", "year": 2026, "payload": "Z" * 1900})

        wt = db.command("serverStatus")["wiredTiger"]["cache"]
        max_b = wt["maximum bytes configured"]
        used_b = wt["bytes currently in the cache"]
        read_into = wt["pages read into cache"]
        requested = max(1, wt["pages requested from the cache"])
        hit_ratio = max(0.0, (1.0 - (read_into / requested)) * 100)
        print(f"[T+{step*10}s] Cache Used: {used_b/(1024*1024):.2f}/{max_b/(1024*1024):.2f} MB | Hit Ratio: {hit_ratio:.4f}%")
        if step < cycles:
            time.sleep(10)

if __name__ == "__main__":
    monitor_cache()
