"""
Activity 7.1 (Try It Yourself): Redesign Referencing Relationship (source_id) as Embedded Subdocument
"""
import json
import os
from pymongo import MongoClient, ASCENDING, DESCENDING

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = MongoClient(MONGO_URI)["cti_digest_prod"]

def redesign_embedded_source():
    db.threats_embedded_source.drop()
    dump_path = os.path.join(os.path.dirname(__file__), "..", "Lab_7_1_Schema_Analysis", "cti_digest_dump.json")
    with open(dump_path) as f:
        dump = json.load(f)

    source_lookup = {s["_id"]: s for s in dump["sources"]}
    redesigned_docs = []
    for t in dump["threats"]:
        doc = dict(t)
        src = source_lookup.get(doc.pop("source_id"), {})
        doc["source"] = {
            "source_id": src.get("_id"),
            "name": src.get("name"),
            "reliability_score": src.get("reliability_score"),
            "verified": src.get("verified"),
            "is_actual_threat": src.get("reliability_score", 0) >= 0.80
        }
        redesigned_docs.append(doc)

    db.threats_embedded_source.insert_many(redesigned_docs)
    db.threats_embedded_source.create_index([("source.is_actual_threat", ASCENDING), ("severity", DESCENDING)])

    actual_threats = list(db.threats_embedded_source.find({"source.is_actual_threat": True}, {"_id": 0}))
    out_path = os.path.join(os.path.dirname(__file__), "embedded_threats_output.json")
    with open(out_path, "w") as f:
        json.dump(actual_threats, f, indent=2)
    print(f"Exported {len(actual_threats)} verified actual threats without $lookup.")

if __name__ == "__main__":
    redesign_embedded_source()
