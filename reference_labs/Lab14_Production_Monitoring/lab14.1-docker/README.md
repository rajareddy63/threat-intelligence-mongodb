# Lab 14.1 — Python MongoDB monitoring dashboard

The Compose stack starts a three-member authenticated MongoDB replica set and a
Python monitoring dashboard. Run `scripts/Initialize-Lab.ps1`, then
`docker compose up --build -d`.

The dashboard is available at `http://localhost:8080`. It samples and logs
connection counts, opcounters, WiredTiger cache usage, replica-set status, and
secondary replication lag every 30 seconds. Cache use at or above 80% and
replication lag above 10 seconds raise warnings. Set `ALERT_WEBHOOK_URL` in the
ignored `.env` file to configure the JSON webhook destination.

Logs are in `logs/monitor.jsonl`. Run checks with:

```powershell
docker compose run --rm dashboard python -m unittest -v test_app
docker compose run --rm dashboard python app.py smoke-test
```

See the root README for Lab 14.2 backup, restore-verification, and benchmark
commands.
