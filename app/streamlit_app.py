import os, uuid, requests, streamlit as st
API=os.getenv("API_URL","http://backend:8000")
st.set_page_config(page_title="Threat Intelligence Assistant",page_icon="🛡️",layout="wide")
st.title("🛡️ Threat Intelligence & Vulnerability Assistant")
st.caption("MongoDB • Ollama • RAG over Labs 7–18 • Local read-only host scanner")
sid=st.session_state.setdefault("session_id",str(uuid.uuid4()))
if "messages" not in st.session_state:st.session_state.messages=[]
with st.sidebar:
 st.subheader("System status")
 try:
  h=requests.get(API+"/api/health",timeout=3).json()
  st.write("MongoDB:", "🟢" if h.get("mongodb") else "🔴")
  st.write("Ollama:", "🟢" if h.get("ollama") else "🟠")
  st.caption(f"Chat model: {h.get('chat_model')}")
 except Exception as e:st.error(f"Backend unavailable: {e}")
 platform=st.selectbox("Target platform",["Windows","Linux","macOS","Android","iOS"])
 st.markdown("---")
 st.subheader("Local scanning")
 st.write("Run the read-only scanner on your laptop (outside Docker).")
 st.code("python agent/host_scanner.py --platform Windows",language="powershell")
 if st.button("Refresh latest scan"):
  try:st.session_state.scan=requests.get(API+"/api/scans/latest",timeout=5).json()
  except Exception as e:st.error(str(e))
 if st.session_state.get("scan"):
  s=st.session_state.scan
  st.write(f"Findings: {len(s.get('findings',[]))}")
  for f in s.get("findings",[]):
   st.write(f"**{f.get('severity','').upper()}** — {f.get('title')}")
  if s.get("findings"):
   st.markdown("**Review a finding**")
   opts={f"{f.get('severity','').upper()} — {f.get('title')}":f.get("finding_id") for f in s["findings"]}
   selected=st.selectbox("Finding to review",list(opts.keys()),key="approval_finding")
   st.caption("Approval records your intent only. No command will run and no system setting will change.")
   phrase=st.text_input("Type I UNDERSTAND THE RISK to record approval",key="approval_phrase")
   if st.button("Record remediation approval"):
    try:
     result=requests.post(API+"/api/remediation/approve",json={"finding_id":opts[selected],"approved":True,"confirmation_phrase":phrase},timeout=8)
     if result.ok:st.success(result.json().get("message"))
     else:st.error(result.text)
    except Exception as e:st.error(str(e))
st.subheader("Threat dashboard")
try:
 t=requests.get(API+"/api/threats",params={"limit":100,"platform":platform},timeout=5).json().get("results",[])
 cols=st.columns(4)
 for col,status in zip(cols,["Active","Evolving","Anticipated","Resolved"]):
  col.metric(status,sum(1 for x in t if x.get("status","Active").lower()==status.lower()))
 with st.expander("Threat records"):
  st.dataframe([{k:x.get(k) for k in ["title","platform","severity","status","source","updated_at"]} for x in t],use_container_width=True)
except Exception as e:st.info("Threat records will appear after the first scan or ingestion.")
st.subheader("Ask using Labs 7–18 and your latest scan")
for m in st.session_state.messages:
 with st.chat_message(m["role"]):st.markdown(m["content"])
if prompt:=st.chat_input("Ask about a CVE, error, threat, or mitigation procedure..."):
 st.session_state.messages.append({"role":"user","content":prompt})
 with st.chat_message("user"):st.markdown(prompt)
 with st.chat_message("assistant"):
  with st.spinner("Searching MongoDB knowledge and consulting Ollama..."):
   try:
    r=requests.post(API+"/api/chat",json={"message":prompt,"session_id":sid,"platform":platform},timeout=190)
    r.raise_for_status();data=r.json();answer=data["answer"]
    if data.get("sources"):answer+="\n\n**Retrieved lab sources:**\n"+", ".join(f"{x['lab']} ({x['source']})" for x in data["sources"])
   except Exception as e:answer=f"Backend error: {e}"
   st.markdown(answer)
 st.session_state.messages.append({"role":"assistant","content":answer})
