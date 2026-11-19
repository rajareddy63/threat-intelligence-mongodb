# Lab 13.1 — MongoDB replica set with Docker Compose

Three MongoDB 7.0 nodes use independent named data volumes, internal DNS, keyfile-based member authentication, root credentials generated locally, and health checks. Published MongoDB and monitoring ports bind to loopback only. The `Initialize-Lab.ps1` script generates a random 756-byte keyfile and a 256-bit hex password under ignored paths. A one-shot Alpine service copies the keyfile into a named volume with MongoDB's expected UID and `0400` permissions; Windows host-file ACLs are not relied upon for Linux container permissions.

The official Mongo image creates the configured root account on each fresh node. The PyMongo initializer then configures `rs0` and waits for one primary and two secondaries. Initialization is idempotent on an already configured set.

## Requirements

- Docker Desktop using Linux containers, Docker Compose v2, and PowerShell 5.1 or later.
- Network access to pull the MongoDB, Alpine, Python, and optional monitoring images.
- Python 3.12 is included in the demonstration image; no host Python packages are needed for the client.

## Start and verify

From this directory:

```powershell
.\scripts\Initialize-Lab.ps1
docker compose up -d mongo1 mongo2 mongo3
docker compose --profile init run --rm replica-set-init
docker compose ps
docker compose run --rm client status
docker compose run --rm client write-read
```

If this Windows account's PowerShell execution policy blocks local scripts, use a temporary process-scoped policy appropriate for trusted local lab files (for example `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`). It resets when that PowerShell session closes; do not lower machine-wide policy for this exercise.

Ports `37017`, `37018`, and `37019` on `127.0.0.1` address nodes 1–3 respectively. They are intentionally separate from conventional local MongoDB ports so the lab will not collide with MongoDB services from other labs. Override the `MONGO*_HOST_PORT` entries in `.env` if needed. If the replica-set initializer image has not yet been built, Compose builds it. Do not remove the named volumes when stopping the exercise.

## Controlled failover

Run `docker compose run --rm client failover`. The PyMongo client records the old primary, asks it to step down, waits for a different primary, and verifies a database write/read after election. The induced, intentional election briefly interrupts writes; it does not delete data. A useful separate resiliency check is `docker compose stop mongo2; docker compose ps; docker compose start mongo2`.

## Activity 13.1 — Prometheus

Run `docker compose --profile monitoring up -d`. Open `http://localhost:9090` and query `mongodb_up`, `mongodb_ss_connections`, or `mongodb_replset_member_health`. Scrape endpoint: `http://localhost:9216/metrics`. Stop only these services with `docker compose --profile monitoring stop`; do not run `docker compose down -v` if you want to retain database files.

## Troubleshooting and security

- Compose requires the ignored `.env` and `secrets/keyfile`; generate them with `Initialize-Lab.ps1`.
- For a failed bootstrap, inspect `docker compose logs mongo1 mongo2 mongo3 replica-set-init`. The expected keyfile ownership and mode inside the Mongo containers are `999:999` and `0400`.
- MongoDB ports and Prometheus ports are loopback-only. The sample root account is solely for a local lab. Never publish `.env` or `secrets/`.
- The image tag for the submission demo is `mongodb-lab13-demo:1.0.0`. Build/test and Docker Hub publishing require a running Docker daemon.

## Reference

Professor-provided [Docker Compose reference](https://github.com/sujeetjagtap/NoSQL-Databases-using-MongoDB/blob/main/chapter-13/docker-compose-production.yml), improved with generated secrets, correct container-side keyfile permissions, isolated ports, persistent per-node volumes, readiness-aware orchestration, and automated initialization.
