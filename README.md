# Threat Intelligence & Vulnerability Assistant

A local-first defensive security application built around **MongoDB + Ollama + FastAPI + Streamlit + Docker**. The application incorporates the supplied MongoDB Labs 7–18 as searchable reference knowledge and adds a read-only host scanner for Windows/Linux.

> Educational assessment build. A scan is an inventory and configuration review, not a guarantee that a machine is clean. No remediation command is executed automatically.

## 1. Architecture

```text
Windows/Linux host
  └── agent/host_scanner.py (read-only inventory)
          │ POST /api/scan-results
          ▼
Docker Compose
  ├── frontend: Streamlit chat/dashboard (8501)
  ├── backend: FastAPI RAG + API (8000)
  │     ├── Ollama chat model (host Ollama at 11434)
  │     ├── Ollama embedding model (optional, locally stored)
  │     ├── reference_labs/ (Labs 7–18, baked into the image)
  │     └── MongoDB collections:
  │           knowledge, sessions, threats, scans,
  │           remediation_approvals, rate_limits
  ├── mongo: MongoDB 7 (persistent named volume)
  └── prometheus (optional monitoring profile)
```

The backend and frontend use the **same custom image** `threat-intelligence-mongodb:1.0`. The original Labs 7–18 source/reference files are copied into that image and ingested into MongoDB knowledge chunks at first startup. MongoDB remains a separate database service, and Ollama is reused from the host so model weights are not duplicated in Docker.

## 2. Requirements

- Docker Desktop with Docker Compose v2
- Ollama installed and running on the host
- Python 3.10+ on the host for the scanner
- Recommended: 8 GB+ RAM for the combined Docker + local model workload; smaller quantized models can be used if available

### Ollama model selection

The defaults are examples, not assumptions about which models you already have. The backend checks `/api/tags`; if the configured chat model is absent, it automatically selects the first installed non-embedding model. To force your preferred local model, set its exact name in `.env`. Check your local models:

```powershell
ollama list
```

Pull only if you do not already have a suitable model:

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Set `OLLAMA_CHAT_MODEL` in `.env` to the exact name from `ollama list`. You can use any Ollama chat model that your machine can run. The embedding model is optional; the app still has MongoDB text retrieval if embedding calls are unavailable.

**Docker Desktop note:** Ollama must listen on an address reachable from containers. The default URL is `http://host.docker.internal:11434`. If Ollama is bound only to loopback and the container cannot reach it, configure Ollama to listen on the host interface or use a supported local networking setup. Do not expose Ollama to an untrusted network.

## 3. Run the application (Windows PowerShell)

```powershell
cd threat-intelligence-mongodb
Copy-Item .env.example .env
# Edit .env and choose your installed Ollama model names
docker compose up --build -d
docker compose ps
```

Open:
- Chat/dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

First startup reads the reference files for Labs 7–18, chunks the text, and inserts it into MongoDB. This can take time when Ollama embeddings are enabled. The application logs show ingestion progress. If it starts without Ollama, it still supports text retrieval and a clearly labelled retrieval-only fallback answer.

Stop without deleting data:

```powershell
docker compose down
```

Reset all stored MongoDB data (destructive):

```powershell
docker compose down -v
```

## 4. Scan your own laptop (read-only)

The scanner must run **on the host**, not inside the backend container. This is intentional: the container cannot safely or reliably inspect the host OS by itself.

Windows PowerShell:

```powershell
python -m pip install requests
python agent/host_scanner.py --platform Windows
```

Linux:

```bash
python3 -m pip install requests
python3 agent/host_scanner.py --platform Linux
```

The scanner collects selected configuration and patch-inventory evidence, then posts findings to MongoDB through the API. It does not install updates, change firewall settings, alter registry values, kill processes, or run exploit tests. Some checks may return “could not verify” depending on privileges and installed tools. Run only on systems you own or are authorized to assess.

### Current scanner coverage

- Windows: Defender status, Windows Firewall profile state, recent hotfix inventory, basic Windows Update status visibility
- Linux: distribution inventory, available APT package updates, UFW state (if installed), selected SSH daemon configuration

This is an initial baseline scanner, not a full vulnerability scanner. It does not replace Microsoft Defender, an authenticated vulnerability scanner, endpoint detection, or a formal penetration test. It does not currently scan macOS, Android, or iOS.

## 5. Threat lifecycle and remediation safety

Threat records support these lifecycle labels:
- **Anticipated** — advisory/watch item; applicability not yet confirmed
- **Active** — current finding or confirmed active incident requiring triage
- **Evolving** — investigation or threat intelligence is changing
- **Resolved** — resolution has been verified by a follow-up check

Synthetic dashboard examples are explicitly marked `synthetic_demo`; they are not real threat alerts. Local scan results are marked `local_scanner`.

The approval endpoint records an explicit user approval only after the phrase `I UNDERSTAND THE RISK` is supplied. It **does not execute** a fix. Review the proposed action, backups, business impact, and rollback plan before applying changes manually. This is safer for a laptop assessment than granting a chat model unrestricted administrator/root access.

## 6. RAG and MongoDB notes

- Lab files are split into overlapping text chunks and stored in `knowledge`.
- If the configured Ollama embedding model is reachable, embeddings are stored with the chunks.
- Portable local retrieval uses MongoDB's text index, so this project works with MongoDB Community.
- Atlas Vector Search can be added by configuring a compatible Atlas deployment and a vector index; the self-hosted Community database does not implement Atlas `$vectorSearch`.
- Conversation messages are persisted in `sessions`.
- Threat records, local scan history, approvals, and rate-limit counters are persisted in separate collections.
- The chat endpoint retrieves relevant lab chunks and the latest scan findings before calling Ollama.

## 7. Lab 7–18 integration map

| Lab | Source material included | Integration in final app |
|---|---|---|
| 7 CTI | CTI backend, frontend, threat schema/analysis and working-set exercises | Threat collection, CTI concepts and lifecycle dashboard |
| 8 Replication | Replica-set deployment, arbiter/priority, failover exercises | MongoDB operational knowledge and resilient deployment design |
| 9 Write concern/partitioning | Write concern and network partition exercises | Reliability/consistency reference knowledge |
| 10 Transactions | Bank transfer and inventory reservation transaction labs | Transactional safety concepts for state-changing workflows |
| 11 Sharding | Sharded cluster, shard initialization and analysis scripts | Scale-out architecture reference |
| 12 Security/TLS | Authentication, role and TLS labs | Credential handling, access-control and TLS guidance |
| 13 Deployment | Compose replica set, Kubernetes StatefulSet, monitoring and Terraform | Container deployment and health-check concepts |
| 14 Production | Monitoring, alerts, backup/restore verification, benchmarks | Health/metrics endpoint, Prometheus profile, operational guidance |
| 15 Multi-tenant SaaS | Tenant-scoped API, rate limiting, migration/rollback | API rate limiting and tenant-safe data design reference |
| 16 Hybrid DB | MongoDB/Cassandra/Neo4j models and query service | Hybrid data-modeling and comparison knowledge |
| 17 Vector RAG | Chunking, local/remote embeddings, retrieval, memory, benchmark | Core RAG ingestion and conversational memory design |
| 18 Comparative capstone | Synthetic CTI event generator and Mongo/Cassandra/Neo4j benchmark | Threat event schema, lifecycle and comparative database concepts |

The original reference folders are retained under `reference_labs/` inside the repository and are copied into the Docker image. Secrets, `.env` files, private keyfiles, local caches, and backup archives are intentionally excluded from the integrated copy.

## 8. API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | MongoDB/Ollama readiness |
| GET | `/api/metrics` | Prometheus metrics |
| POST | `/api/chat` | RAG chat with MongoDB memory |
| GET | `/api/threats` | Threat lifecycle records |
| POST | `/api/threats` | Add/update a threat record |
| POST | `/api/scan-results` | Receive local scanner results |
| GET | `/api/scans/latest` | Latest host scan |
| POST | `/api/remediation/approve` | Record confirmation; never runs commands |
| POST | `/api/admin/ingest` | Re-ingest Labs 7–18 knowledge |

## 9. Monitoring

```powershell
docker compose --profile monitoring up -d
```

Prometheus: http://localhost:9090  
Metrics endpoint: http://localhost:8000/api/metrics

## 10. Tests and validation

Run Python syntax checks:

```powershell
python -m compileall app agent
```

Check backend readiness and APIs after Compose starts:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod http://localhost:8000/api/threats
```

Try a chat:

```powershell
$body = @{ message = "Explain how Labs 12 and 17 contribute to secure threat intelligence"; session_id = "demo"; platform = "Windows" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/chat -ContentType "application/json" -Body $body
```

## 11. Assessment demonstration checklist

1. Show `ollama list` and the selected local model.
2. Run `docker compose up --build -d`; show the same custom image used by backend and frontend.
3. Open the Streamlit dashboard and `/api/health`.
4. Show MongoDB collections: `knowledge`, `sessions`, `threats`, `scans`, `remediation_approvals`.
5. Ask a question specifically about Lab 12, Lab 14, Lab 15, and Lab 17; show retrieved source references.
6. Run the Windows/Linux host scanner and show the findings persisted in MongoDB.
7. Ask the chat to explain one finding and request a safe remediation procedure.
8. Demonstrate that an approval is recorded but no host command is run.
9. Show Prometheus metrics and the API health endpoint.
10. Show the Lab 7–18 integration map and the original reference folders.

## 12. Private GitHub submission

Create a **private** GitHub repository, then:

```powershell
git init
git add .
git status
# Confirm .env, passwords, keyfiles, tokens, and local secrets are NOT staged.
git commit -m "Build MongoDB Ollama threat intelligence assistant"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_PRIVATE_REPO.git
git push -u origin main
```

Invite the faculty collaborator through GitHub repository Settings → Collaborators. Replace the placeholder repository URL in the submission PDF with the actual private repository URL before uploading it to the course portal.

## Security disclaimer

Use this project only on devices and networks you own or are authorized to assess. Findings are advisory and may include false positives or incomplete checks. Verify vendor advisories and CVE applicability before making changes. Never paste passwords, private keys, access tokens, or sensitive logs into the chat.
