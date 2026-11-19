# Exercise 14 — MongoDB Production Operations

Two Docker-based labs demonstrate production monitoring, alerting, automated
backups, restore verification, and measured performance.

## Requirements

- Docker Desktop with Docker Compose
- PowerShell 5.1+
- Access to pull the `mongo:7.0` and `python:3.12-slim` base images

## Initialize and start the replica set and dashboard

```powershell
cd C:\Users\rajar\Downloads\MongoDB_Exercise14_Production\lab14.1-docker
.\scripts\Initialize-Lab.ps1
docker compose up --build -d
docker compose ps
```

Initialization creates a MongoDB keyfile and a private `.env` file containing
random credentials. The file is ignored by Git. MongoDB ports are bound only to
loopback (`37117`–`37119`); the dashboard is at
`http://localhost:8080`.

## Lab 14.1 — Monitoring dashboard

Open the dashboard at `http://localhost:8080`. It presents live connection
counts, opcounters, WiredTiger cache usage, replica-set member state, and
secondary replication lag. Metrics are sampled and written to
`lab14.1-docker/logs/monitor.jsonl` every 30 seconds. Cache usage at or above
80% and replication lag above 10 seconds produce warnings and POST JSON webhook
alerts. Configure `ALERT_WEBHOOK_URL` in the ignored `.env` file to route alerts
to a real receiver.

Run the app tests and basic insert/read check:

```powershell
docker compose run --rm dashboard python -m unittest -v test_app
docker compose run --rm dashboard python app.py smoke-test
```

## Lab 14.2 — Automated backup and benchmark

Create and restore-verify one backup:

```powershell
cd ..\lab14.2-backup-benchmark
.\Run-Backup.ps1
```

Start the hourly scheduler with `.\Run-Backup.ps1 -Schedule`. Archives are
retained for seven days under `lab14.2-backup-benchmark/backups/`; each newly
created archive is restored to a temporary database and document counts are
compared before it is declared verified.

Run actual 1,000 / 10,000 / 100,000-document insert and read benchmarks:

```powershell
.\Run-Benchmark.ps1
```

Measured results are written to `lab14.2-backup-benchmark/results/benchmark.json`.

## One Docker image for both labs

The combined image includes the Python dashboard, PyMongo benchmarks, `mongodump`,
`mongorestore`, backup verification, and the hourly scheduler:
`raja6303/mongodb-exercise14:1.0.0`.

Public Docker Hub page:
https://hub.docker.com/r/raja6303/mongodb-exercise14

The MongoDB replica set must be running on the Compose network first:

```powershell
docker compose -f lab14.1-docker/docker-compose.yml up -d
docker pull raja6303/mongodb-exercise14:1.0.0
docker run --rm --network lab141-docker_mongo-net --env-file lab14.1-docker/.env -p 127.0.0.1:8081:8080 raja6303/mongodb-exercise14:1.0.0 dashboard
```

In another PowerShell window, run a verified backup with the same image:

```powershell
docker run --rm --network lab141-docker_mongo-net --env-file lab14.1-docker/.env -e BACKUP_DIR=/backups -v "${PWD}/lab14.2-backup-benchmark/backups:/backups" raja6303/mongodb-exercise14:1.0.0 backup
```

For the required write/read benchmarks:

```powershell
docker run --rm --network lab141-docker_mongo-net --env-file lab14.1-docker/.env -e BENCHMARK_RESULTS_PATH=/results/benchmark.json -v "${PWD}/lab14.2-backup-benchmark/results:/results" raja6303/mongodb-exercise14:1.0.0 benchmark --counts 1000 10000 100000
```

The image was built, both modes were tested locally with `docker run`, pushed
with approval, and verified on Docker Hub. The final report and genuine runtime
screenshots are in `reports/` and `screenshots/`.
