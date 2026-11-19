"""
Lab 7.2: Working Set Analysis (100,000 documents @ ~2 KB each)
Dataset: https://github.com/jacobdjwilson/awesome-annual-security-reports/
"""
import os
import random
from pymongo import MongoClient, ASCENDING, DESCENDING

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = MongoClient(MONGO_URI)["cti_digest_prod"]
COL = "annual_reports_workingset"

VENDORS = ["Mandiant", "CrowdStrike", "Verizon", "Palo Alto Unit 42", "Recorded Future", "Sophos"]
CATEGORIES = ["Global Threat Intelligence", "Ransomware", "Cloud Security", "Data Breaches", "AI Security"]

def build_2kb_doc(idx: int) -> dict:
    doc = {
        "report_id": f"RPT-2026-{idx:06d}",
        "vendor": random.choice(VENDORS),
        "category": random.choice(CATEGORIES),
        "year": random.randint(2019, 2026),
        "title": f"Annual Security Report Telemetry #{idx}",
        "source_repo": "https://github.com/jacobdjwilson/awesome-annual-security-reports/",
        "summary": "X" * 900,
        "telemetry_blob": "Y" * 900
    }
    return doc

def run_lab_7_2():
    col = db[COL]
    col.drop()
    for start in range(0, 100_000, 5000):
        col.insert_many([build_2kb_doc(i) for i in range(start, start + 5000)], ordered=False)
    col.create_index([("report_id", ASCENDING)], unique=True)
    col.create_index([("category", ASCENDING), ("year", DESCENDING)])

    stats = db.command("collStats", COL)
    wt = db.command("serverStatus")["wiredTiger"]["cache"]
    print(f"Docs: {stats['count']} | Avg Size: {stats['avgObjSize']} B | Storage: {stats['storageSize']/(1024*1024):.2f} MB")
    print(f"WT Max Cache: {wt['maximum bytes configured']/(1024*1024):.2f} MB | Used: {wt['bytes currently in the cache']/(1024*1024):.2f} MB")

if __name__ == "__main__":
    run_lab_7_2()
