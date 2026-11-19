from __future__ import annotations
import os, re, time, uuid, logging, platform, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient, ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import PyMongoError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
log=logging.getLogger("threatintel")
MONGO_URI=os.getenv("MONGO_URI","mongodb://mongo:27017")
DB_NAME=os.getenv("MONGO_DB","threat_intelligence")
OLLAMA_URL=os.getenv("OLLAMA_BASE_URL","http://host.docker.internal:11434").rstrip("/")
CHAT_MODEL=os.getenv("OLLAMA_CHAT_MODEL","llama3.2:3b")
EMBED_MODEL=os.getenv("OLLAMA_EMBED_MODEL","nomic-embed-text")
USE_OLLAMA=os.getenv("USE_OLLAMA","true").lower()=="true"
RATE_LIMIT=int(os.getenv("RATE_LIMIT_PER_MINUTE","30"))
KNOWLEDGE_DIR=Path(os.getenv("KNOWLEDGE_DIR","/app/reference_labs"))
app=FastAPI(title="Threat Intelligence Assistant",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:8501","http://127.0.0.1:8501"],allow_methods=["*"],allow_headers=["*"])
mongo=MongoClient(MONGO_URI,serverSelectionTimeoutMS=4000)
db=mongo[DB_NAME]
knowledge=db["knowledge"]; sessions=db["sessions"]; threats=db["threats"]; scans=db["scans"]; approvals=db["remediation_approvals"]; rate=db["rate_limits"]
REQUESTS=Counter("http_requests_total","HTTP requests",["method","path","status"])
LATENCY=Histogram("http_request_duration_seconds","HTTP request latency")
class RateLimitMiddleware(BaseHTTPMiddleware):
 async def dispatch(self,request,call_next):
  started=time.time()
  if request.url.path.startswith("/api/") and request.url.path not in ("/api/health","/api/metrics"):
   client=request.client.host if request.client else "unknown"
   bucket=int(time.time()//60)
   key=f"{client}:{bucket}"
   try:
    row=rate.find_one_and_update({"_id":key},{"$inc":{"count":1},"$setOnInsert":{"created_at":datetime.now(timezone.utc)}},upsert=True,return_document=ReturnDocument.AFTER)
    if row and row.get("count",0)>RATE_LIMIT:
     return Response('{"detail":"Rate limit exceeded"}',status_code=429,media_type="application/json")
   except Exception: pass
  response=await call_next(request)
  REQUESTS.labels(request.method,request.url.path,str(response.status_code)).inc()
  LATENCY.observe(time.time()-started)
  return response
app.add_middleware(RateLimitMiddleware)
class ChatIn(BaseModel):
 message:str=Field(min_length=2,max_length=5000)
 session_id:str="default"
 platform:str="Windows"
class ScanIn(BaseModel):
 platform:str="Windows"
 findings:list[dict[str,Any]]
 host:str="local-host"
class ApproveIn(BaseModel):
 finding_id:str
 approved:bool
 confirmation_phrase:str=""
def now(): return datetime.now(timezone.utc)
def safe_json(obj):
 from bson import ObjectId
 if isinstance(obj,ObjectId): return str(obj)
 if isinstance(obj,datetime): return obj.isoformat()
 if isinstance(obj,dict): return {k:safe_json(v) for k,v in obj.items() if k!="_id"}
 if isinstance(obj,list): return [safe_json(x) for x in obj]
 return obj
def ensure_indexes():
 knowledge.create_index([("lab",ASCENDING),("source",ASCENDING)])
 knowledge.create_index([("text", "text")])
 sessions.create_index([("session_id",ASCENDING),("timestamp",DESCENDING)])
 threats.create_index([("platform",ASCENDING),("status",ASCENDING),("severity",DESCENDING)])
 scans.create_index([("host",ASCENDING),("scanned_at",DESCENDING)])
 approvals.create_index([("finding_id",ASCENDING),("created_at",DESCENDING)])
def chunk_words(text,size=180,overlap=30):
 words=text.split()
 for i in range(0,len(words),size-overlap):
  part=words[i:i+size]
  if not part: break
  yield " ".join(part)
def available_ollama_models():
 try:
  r=requests.get(f"{OLLAMA_URL}/api/tags",timeout=3);r.raise_for_status()
  return [x.get("name","") for x in r.json().get("models",[]) if x.get("name")]
 except Exception:return []
def effective_chat_model():
 models=available_ollama_models()
 if CHAT_MODEL in models:return CHAT_MODEL
 candidates=[m for m in models if not any(k in m.lower() for k in ("embed","bge","rerank"))]
 return candidates[0] if candidates else CHAT_MODEL
def ollama_embed(text):
 if not USE_OLLAMA:return None
 try:
  r=requests.post(f"{OLLAMA_URL}/api/embeddings",json={"model":EMBED_MODEL,"prompt":text[:6000]},timeout=45)
  r.raise_for_status(); return r.json().get("embedding")
 except Exception as e:
  log.warning("Ollama embedding unavailable: %s",e); return None
def ingest_reference_labs(force=False):
 if not KNOWLEDGE_DIR.exists(): return {"ingested":0,"reason":"reference directory missing"}
 existing=knowledge.count_documents({})
 if existing and not force:return {"ingested":0,"already_present":existing}
 if force:knowledge.delete_many({})
 count=0
 for path in KNOWLEDGE_DIR.rglob("*"):
  if not path.is_file() or path.suffix.lower() not in {".md",".txt",".py",".js",".json",".yml",".yaml",".cql",".cypher",".html"}:continue
  try:
   text=path.read_text(encoding="utf-8",errors="ignore")
   if len(text.strip())<80:continue
   rel=path.relative_to(KNOWLEDGE_DIR).as_posix()
   lab=rel.split("/",1)[0]
   for idx,chunk in enumerate(chunk_words(text)):
    doc={"doc_id":hashlib_id(rel+str(idx)),"lab":lab,"source":rel,"chunk_index":idx,"text":chunk,"created_at":now()}
    emb=ollama_embed(chunk)
    if emb:doc["embedding"]=emb
    knowledge.update_one({"doc_id":doc["doc_id"]},{"$set":doc},upsert=True);count+=1
  except Exception as e: log.warning("Skip %s: %s",path,e)
 return {"ingested":count}
def hashlib_id(value):
 import hashlib
 return hashlib.sha256(value.encode()).hexdigest()
def retrieve(query,limit=5):
 # MongoDB text index provides portable local retrieval; Ollama embeddings are stored for Atlas/vector-ready deployments.
 try:
  results=list(knowledge.find({"$text":{"$search":query}},{"score":{"$meta":"textScore"},"text":1,"lab":1,"source":1}).sort([("score",{"$meta":"textScore"})]).limit(limit))
  if results:return results
 except Exception:pass
 terms={t.lower() for t in re.findall(r"[a-zA-Z0-9_-]{3,}",query)}
 scored=[]
 for d in knowledge.find({},{"text":1,"lab":1,"source":1}).limit(5000):
  words=set(re.findall(r"[a-zA-Z0-9_-]{3,}",d.get("text","").lower()))
  score=len(terms&words)
  if score:scored.append((score,d))
 return [x[1] for x in sorted(scored,key=lambda x:x[0],reverse=True)[:limit]]
def ollama_chat(prompt,context,history):
 if not USE_OLLAMA:return None
 messages=[{"role":"system","content":"You are a defensive threat-intelligence assistant. Use only supplied lab and scan evidence for factual claims. Clearly distinguish observed findings from general advice. Never claim a scan proved compromise. Give safe, reversible mitigation steps. Never execute remediation."}]
 for h in history[-6:]: messages.append({"role":h["role"],"content":h["content"]})
 messages.append({"role":"user","content":f"PLATFORM: {prompt.get('platform','Windows')}\\nEVIDENCE FROM LABS 7-18 AND SCANS:\\n{context}\\n\\nQUESTION: {prompt['message']}\\n\\nIf evidence is insufficient, say so and state what to check next."})
 try:
  r=requests.post(f"{OLLAMA_URL}/api/chat",json={"model":effective_chat_model(),"messages":messages,"stream":False,"options":{"temperature":0.2}},timeout=180)
  r.raise_for_status();return r.json().get("message",{}).get("content")
 except Exception as e:
  log.warning("Ollama chat unavailable: %s",e);return None
def fallback_answer(message,docs,platform):
 evidence="\n\n".join(f"[{d.get('lab')} / {d.get('source')}]\n{d.get('text','')[:900]}" for d in docs)
 if not evidence:evidence="No matching Lab 7–18 reference chunk was found."
 return f"Local Ollama is unavailable, so this is a retrieval-only response (not generated AI).\n\nPlatform: {platform}\n\nRelevant lab evidence:\n{evidence}\n\nQuestion: {message}\n\nNext step: provide the exact error, CVE, event log, or scanner finding so I can map it to the lab evidence and suggest a verified defensive procedure."
@app.on_event("startup")
def startup():
 try:
  mongo.admin.command("ping");ensure_indexes()
  if knowledge.count_documents({})==0:
   result=ingest_reference_labs();log.info("Lab knowledge ingestion: %s",result)
  if threats.count_documents({})==0:
   samples=[
    {"threat_id":"demo-win-anticipated","title":"Illustrative: Windows security patch advisory watch","summary":"Synthetic demonstration record representing a newly disclosed vulnerability awaiting local applicability validation.","platform":"Windows","severity":"medium","status":"Anticipated","source":"synthetic_demo","category":"vulnerability"},
    {"threat_id":"demo-win-active","title":"Illustrative: Endpoint protection disabled","summary":"Synthetic demonstration record. A local scan is required to establish whether this condition exists on the host.","platform":"Windows","severity":"high","status":"Active","source":"synthetic_demo","category":"endpoint_protection"},
    {"threat_id":"demo-linux-evolving","title":"Illustrative: SSH hardening review","summary":"Synthetic demonstration record representing a configuration risk under investigation.","platform":"Linux","severity":"medium","status":"Evolving","source":"synthetic_demo","category":"remote_access"},
    {"threat_id":"demo-resolved","title":"Illustrative: Firewall configuration reviewed","summary":"Synthetic demonstration record showing a resolved lifecycle state; not evidence of a real remediation.","platform":"All","severity":"low","status":"Resolved","source":"synthetic_demo","category":"firewall"}
   ]
   for sample in samples: sample["updated_at"]=now()
   threats.insert_many(samples)
 except Exception as e:log.exception("Startup initialization warning: %s",e)
@app.on_event("shutdown")
def shutdown():mongo.close()
@app.get("/api/health")
def health():
 try:mongo.admin.command("ping");mongo_ok=True
 except Exception:mongo_ok=False
 try:r=requests.get(f"{OLLAMA_URL}/api/tags",timeout=2);ollama_ok=r.ok
 except Exception:ollama_ok=False
 return {"status":"ok" if mongo_ok else "degraded","mongodb":mongo_ok,"ollama":ollama_ok,"chat_model":effective_chat_model(),"configured_chat_model":CHAT_MODEL,"available_models":available_ollama_models(),"embedding_model":EMBED_MODEL}
@app.get("/api/metrics")
def metrics():return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.get("/api/threats")
def list_threats(platform:str|None=None,status:str|None=None,limit:int=100):
 filt={}
 if platform:filt["platform"]={"$in":[platform,"All"]}
 if status:filt["status"]=status
 return {"results":[safe_json(x) for x in threats.find(filt).sort("updated_at",DESCENDING).limit(min(limit,300))]}
@app.post("/api/threats")
def add_threat(item:dict):
 required=("title","summary")
 if not all(item.get(k) for k in required):raise HTTPException(400,"title and summary are required")
 item.update({"threat_id":item.get("threat_id",str(uuid.uuid4())),"created_at":now(),"updated_at":now()})
 threats.update_one({"threat_id":item["threat_id"]},{"$set":item},upsert=True)
 return safe_json(item)
@app.post("/api/scan-results")
def save_scan(payload:ScanIn):
 scan={"scan_id":str(uuid.uuid4()),"host":payload.host,"platform":payload.platform,"findings":payload.findings,"scanned_at":now()}
 scans.insert_one(scan)
 for f in payload.findings:
  tid=f.get("finding_id") or str(uuid.uuid4())
  threat={"threat_id":tid,"title":f.get("title","Local security finding"),"summary":f.get("evidence",""),"platform":payload.platform,"severity":f.get("severity","medium"),"status":f.get("status","Active"),"source":"local_scanner","category":f.get("category","configuration"),"remediation":f.get("remediation","Review the finding and consult your administrator."),"host":payload.host,"updated_at":now(),"scanned_at":now()}
  threats.update_one({"threat_id":tid},{"$set":threat},upsert=True)
 return {"scan_id":scan["scan_id"],"stored_findings":len(payload.findings)}
@app.get("/api/scans/latest")
def latest_scan():
 x=scans.find_one(sort=[("scanned_at",DESCENDING)])
 return safe_json(x) if x else {"message":"No local scan has been submitted yet."}
@app.post("/api/remediation/approve")
def approve(body:ApproveIn):
 if not body.approved:
  approvals.insert_one({"finding_id":body.finding_id,"approved":False,"created_at":now()})
  return {"status":"rejected","message":"No action was performed."}
 # This app intentionally records approval only. It does not execute commands or change host state.
 if body.confirmation_phrase!="I UNDERSTAND THE RISK":
  raise HTTPException(400,"Type the exact confirmation phrase: I UNDERSTAND THE RISK")
 record={"finding_id":body.finding_id,"approved":True,"created_at":now(),"execution":"manual_only","note":"Approval recorded; no remediation command is executed by this application."}
 approvals.insert_one(record)
 return {"status":"approval_recorded","message":"Approval recorded. Apply the documented remediation manually after reviewing backups and impact; this application did not change your system."}

@app.post("/api/chat")
def chat(body:ChatIn):
 history=list(sessions.find(
  {"session_id":body.session_id},
  {"role":1,"content":1}
 ).sort("timestamp",DESCENDING).limit(6))[::-1]

 message=body.message.lower()
 platform=(body.platform or "All").strip()

 threat_request=(
  ("threat" in message or "vulnerab" in message)
  and any(word in message for word in [
   "list","show","record","database","anticipated",
   "active","evolving","resolved","all"
  ])
 )

 if threat_request:
  status_filter=None
  for status in ["Anticipated","Active","Evolving","Resolved"]:
   if status.lower() in message:
    status_filter=status
    break

  query={"platform":{"$in":[platform,"All"]}}
  if status_filter:
   query["status"]=status_filter

  records=list(threats.find(query).sort("updated_at",DESCENDING))

  if not records:
   answer=f"No matching {status_filter or ''} threats are recorded for {platform} in the database."
  else:
   answer=f"## Threats recorded in MongoDB for {platform}\n\n"
   for item in records:
    category=item.get("category","")
    if category=="vulnerability":
     actions="Check the vendor security advisory, validate whether the Windows version is affected, and apply the applicable security update."
    elif category=="endpoint_protection":
     actions="Verify Windows Defender and real-time protection status. Investigate disabled protection, restore it if authorized, and run a security scan."
    elif category=="firewall":
     actions="Review firewall configuration and verify appropriate inbound and outbound security rules."
    else:
     actions="Investigate the finding, validate its applicability, and follow appropriate vendor-recommended security controls."

    answer+=(
     f"### {item.get('title','Untitled threat')}\n"
     f"- **Threat ID:** {item.get('threat_id','Not recorded')}\n"
     f"- **Platform:** {item.get('platform','Not recorded')}\n"
     f"- **Severity:** {item.get('severity','Not recorded')}\n"
     f"- **Status:** {item.get('status','Not recorded')}\n"
     f"- **Database summary:** {item.get('summary','Not recorded')}\n"
     f"- **Source:** {item.get('source','Not recorded')}\n"
     f"- **Recommended defensive actions:** {actions}\n\n"
    )

   answer+=(
    "**Evidence note:** Threat details are retrieved from MongoDB. "
    "Defensive actions are recommendations, not database fields. "
    "Synthetic demonstration records are not confirmed real-world incidents."
   )

  sessions.insert_one({"session_id":body.session_id,"role":"user","content":body.message,"timestamp":now()})
  sessions.insert_one({"session_id":body.session_id,"role":"assistant","content":answer,"timestamp":now()})

  return {
   "answer":answer,
   "sources":[{"lab":"MongoDB threats","source":item.get("source","unknown")} for item in records],
   "session_id":body.session_id,
   "model":"MongoDB threat records"
  }

 docs=retrieve(body.message+" "+body.platform,5)
 scan=scans.find_one(sort=[("scanned_at",DESCENDING)])
 scan_context=""
 if scan:
  scan_context="\nLATEST LOCAL SCAN FINDINGS:\n"+str(scan.get("findings",[])[:20])
 context="\n\n".join(f"[{d.get('lab')} | {d.get('source')}]\n{d.get('text','')}" for d in docs)+scan_context
 answer=ollama_chat({"message":body.message,"platform":body.platform},context,history)
 if not answer:
  answer=fallback_answer(body.message,docs,body.platform)

 sessions.insert_one({"session_id":body.session_id,"role":"user","content":body.message,"timestamp":now()})
 sessions.insert_one({"session_id":body.session_id,"role":"assistant","content":answer,"timestamp":now()})
 return {"answer":answer,"sources":[{"lab":d.get("lab"),"source":d.get("source")} for d in docs],"session_id":body.session_id,"model":effective_chat_model() if USE_OLLAMA else "retrieval-only"}
@app.post("/api/admin/ingest")
def reingest():
 return ingest_reference_labs(force=True)
