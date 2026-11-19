# Lab integration traceability

This table maps the supplied student lab source trees to the final Threat Intelligence Assistant. The original source is retained under `reference_labs/` (excluding secrets, private keyfiles, `.env` files, caches and backup archives).

- **Lab 7 — CTI:** existing CTI API, threat schema, embedded-document redesign and WiredTiger working-set exercises inform threat records, dashboard concepts and CTI retrieval.
- **Lab 8 — Replication:** replica-set deployment, arbiter/priority and failover observer scripts are included as operational reference knowledge.
- **Lab 9 — Write concern/partitioning:** write concern and partition exercises inform durability and partition behavior guidance.
- **Lab 10 — Transactions:** bank-transfer and inventory-reservation examples inform safe transactional workflow guidance.
- **Lab 11 — Sharding:** sharded cluster initialization, data insertion and analysis inform scale-out deployment guidance.
- **Lab 12 — Security/TLS:** authentication, roles and TLS exercises inform credential, authorization and transport-security recommendations.
- **Lab 13 — Deployment:** Docker Compose, replica-set initialization, Prometheus and Kubernetes StatefulSet examples inform deployment and readiness design.
- **Lab 14 — Production:** metrics collection, alerts, backups, restore verification and benchmarks inform health/metrics/monitoring and recovery guidance.
- **Lab 15 — Multi-tenant SaaS:** tenant-scoped records, per-tenant rate limits, migration and rollback inform API controls and tenant isolation.
- **Lab 16 — Hybrid databases:** MongoDB, Cassandra and Neo4j data models and query service inform comparative data architecture explanations.
- **Lab 17 — Vector RAG:** chunking, embeddings, retrieval and conversation memory are the basis for the knowledge pipeline and chat endpoint.
- **Lab 18 — Comparative capstone:** synthetic CTI events and MongoDB/Cassandra/Neo4j benchmarks inform threat event modeling and comparison guidance.

The app indexes textual source files from all twelve lab folders into MongoDB `knowledge`. The RAG response includes the lab folder and source path for retrieved chunks. This provides traceability to the supplied work; it does not mean every original lab's infrastructure (e.g., Cassandra, Neo4j, Kubernetes, or multi-node replica sets) is started in the final Compose stack. The integrated assessment runtime uses one MongoDB service plus one shared application image, as requested, and reuses host Ollama.
