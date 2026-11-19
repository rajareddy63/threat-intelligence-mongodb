# Lab 14.2 — Automated backup and performance benchmarks

This lab uses the replica set and Docker Compose file in `../lab14.1-docker/`.
The combined image `raja6303/mongodb-exercise14:1.0.0` includes this lab's
`mongodump`, `mongorestore`, backup verification, scheduler, and benchmark tasks.

## Run a backup and verify a restore

Start the Exercise 14 replica set first. Then run:

```powershell
docker run --rm --network lab141-docker_mongo-net --env-file ..\lab14.1-docker\.env -e BACKUP_DIR=/backups -v "${PWD}/backups:/backups" raja6303/mongodb-exercise14:1.0.0 backup
```

The script writes a timestamped, compressed `mongodump` archive to `backups/`,
restores it into a temporary verification database, checks each restored
collection's document count against the source, removes the temporary database,
and prunes archives older than seven days.

To keep backups running hourly in a container:

```powershell
docker compose -f ..\lab14.1-docker\docker-compose.yml --profile backup up -d backup-scheduler
docker compose -f ..\lab14.1-docker\docker-compose.yml --profile backup logs -f backup-scheduler
```

The scheduled service takes a backup immediately, verifies it, prunes expired
archives, and repeats after each 3,600-second interval.

## Run the three benchmark sizes

```powershell
docker run --rm --network lab141-docker_mongo-net --env-file ..\lab14.1-docker\.env -e BENCHMARK_RESULTS_PATH=/results/benchmark.json -v "${PWD}/results:/results" raja6303/mongodb-exercise14:1.0.0 benchmark --counts 1000 10000 100000
```

The Python/PyMongo benchmark measures elapsed time and documents per second for
bulk insertion and full cursor reads, verifies the read count, drops each
temporary collection, and writes measured results to `results/benchmark.json`.
No benchmark numbers are pre-filled or simulated.
