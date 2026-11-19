"""
Full-Stack Cyber-Threat Intelligence (CTI) Platform Backend
Features: Threat Search, Automated Threat Classification, Lab 7.1 $bsonSize, Lab 7.2 WiredTiger Monitor
"""
import os, re, time, random
from typing import List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = MongoClient(MONGO_URI)["cti_digest_prod"]

app = FastAPI(title="CTI Digest Intelligence Platform")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ThreatInput(BaseModel):
    title: str
    summary: str
    source_id: str = "src_002"
    actor_id: str = "act_qilin"
    cves: List[str] = []
    iocs: List[str] = []

def classify_threat(title: str, summary: str, verified: bool) -> dict:
    txt = f"{title} {summary}".lower()
    if not verified:
        return {"classification": "Unverified Noise", "severity": "Low", "cvss_score": 3.2, "is_actual_threat": False}
    if any(k in txt for k in ["ransomware", "encrypt", "qilin", "lockbit", "akira"]):
        return {"classification": "Ransomware", "severity": "Critical", "cvss_score": 9.6, "is_actual_threat": True}
    if any(k in txt for k in ["exploit", "zero-day", "rce", "vpn", "cve-"]):
        return {"classification": "Vulnerability Exploitation", "severity": "Critical", "cvss_score": 9.1, "is_actual_threat": True}
    if any(k in txt for k in ["phishing", "clickfix", "infostealer", "powershell"]):
        return {"classification": "Malware / Phishing", "severity": "High", "cvss_score": 8.0, "is_actual_threat": True}
    return {"classification": "Strategic Intelligence", "severity": "Medium", "cvss_score": 6.0, "is_actual_threat": True}

@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))

@app.get("/api/threats")
def search_threats(q: Optional[str] = None, classification: Optional[str] = None, only_actual: bool = False):
    col = db.threats_embedded_source if only_actual else db.threats
    filt = {"source.is_actual_threat": True} if only_actual else {}
    if classification and classification != "All":
        filt["classification"] = classification
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        filt["$or"] = [{"title": rx}, {"summary": rx}, {"cves": rx}, {"iocs.value": rx}]
    return {"results": list(col.find(filt).sort("published_date", DESCENDING).limit(50))}

@app.post("/api/threats/classify")
def add_threat(item: ThreatInput):
    src = db.sources.find_one({"_id": item.source_id}) or {"_id": item.source_id, "name": "Unknown", "reliability_score": 0.4, "verified": False}
    verdict = classify_threat(item.title, item.summary, src.get("verified", False))
    doc = {
        "_id": f"thr_2026_{random.randint(100,9999)}",
        "title": item.title,
        "classification": verdict["classification"],
        "severity": verdict["severity"],
        "cvss_score": verdict["cvss_score"],
        "published_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor_id": item.actor_id,
        "source_id": src["_id"],
        "cves": item.cves,
        "iocs": [{"type": "indicator", "value": i, "confidence": 90} for i in item.iocs],
        "summary": item.summary
    }
    db.threats.insert_one(doc)
    emb = dict(doc)
    emb.pop("source_id")
    emb["source"] = {**src, "is_actual_threat": verdict["is_actual_threat"]}
    db.threats_embedded_source.insert_one(emb)
    return {"verdict": verdict, "document": emb}

@app.get("/api/metrics")
def metrics():
    bson_res = list(db.threats.aggregate([
        {"$project": {"b": {"$bsonSize": "$$ROOT"}}},
        {"$group": {"_id": None, "avg": {"$avg": "$b"}, "max": {"$max": "$b"}}}
    ]))
    wt = db.command("serverStatus").get("wiredTiger", {}).get("cache", {})
    req = max(1, wt.get("pages requested from the cache", 1))
    hit = max(0.0, (1.0 - (wt.get("pages read into cache", 0) / req)) * 100)
    return {
        "avg_bson_bytes": round(bson_res[0]["avg"], 2) if bson_res else 0,
        "max_bson_bytes": bson_res[0]["max"] if bson_res else 0,
        "wt_hit_ratio_pct": round(hit, 4),
        "wt_used_mb": round(wt.get("bytes currently in the cache", 0) / (1024*1024), 2),
        "wt_max_mb": round(wt.get("maximum bytes configured", 0) / (1024*1024), 2)
    }
