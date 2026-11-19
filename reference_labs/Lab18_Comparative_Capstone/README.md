# Exercise 18: Comparative Capstone Lab

A Docker Compose lab comparing the same deterministic synthetic threat-intelligence events in MongoDB, Apache Cassandra, and Neo4j. The Python runner creates schemas and indexes, loads records, runs four benchmark workloads, and writes measured results, vector charts, and a PDF report.

## Requirements

- Docker Desktop with Docker Compose v2 and at least 8 GB RAM assigned to Docker recommended for running all three databases together.
- To run Python locally instead: Python 3.11+ and `pip install -r requirements.txt`.

## Run with Docker

```powershell
# Default: 100,000 records, 10 query/insert repetitions per database
docker compose up --build

# Small end-to-end smoke run
$env:THREAT_RECORDS = '1000'
docker compose up --build

# Stop containers; database data remains in named volumes
docker compose down
```

The `app` task exits after writing `results/benchmark_results.json`, `results/benchmark_results.csv`, `results/benchmark_query_latency.svg`, `results/benchmark_insert_throughput.svg`, and `results/Exercise_18_Final_Submission.pdf`. Use `docker compose logs app` to inspect execution. Database volumes are `mongo_data`, `cassandra_data`, and `neo4j_data`.

For local execution with the databases exposed on localhost (ports avoid common existing lab containers):

```powershell
pip install -r requirements.txt
$env:MONGO_URI = 'mongodb://localhost:27118'
$env:CASSANDRA_HOSTS = 'localhost'
$env:NEO4J_URI = 'bolt://localhost:27687'
python run_all.py --records 100000 --runs 10
```

Host mappings: MongoDB `27118`, Cassandra `29042`, Neo4j Browser `27474`, and Neo4j Bolt `27687`. The Cassandra driver uses port 9042 by default; set `CASSANDRA_PORT=29042` in the environment when running the Python app outside Compose.

Options: `--records`, `--runs`, `--seed`, `--insert-batch-size`, and `--output-dir`. Each database can fail independently; failures are saved rather than turned into fabricated timings. `--insert-batch-size` defaults to 50. Query result fields include medians and successful run counts; insert rates are repeated batch throughput, not per-event latency.

## Database design

- MongoDB: `threatintel.threats`, compound history and target indexes, plus date/source and unique ID indexes.
- Cassandra: query-specific `history_by_indicator`, `target_spread_by_target`, and `daily_volume_by_day` tables. Partition keys are chosen for the corresponding lookups.
- Neo4j: indexed/unique `Threat` nodes and `Target` nodes linked by `TARGETS` relationships.

The executable runner initializes each schema after service health checks. Reference initialization scripts are in `init/`. MongoDB's official image automatically runs its script on a fresh data volume; Cassandra and Neo4j schemas are created by the Python runner (or can be applied manually with `cqlsh` and `cypher-shell`). The lab uses single-node replication settings and is not production-secure.

## Results and interpretation

Only successful measurements in the JSON/CSV are actual. Missing/failed services have no invented scores. The PDF labels 1M, 10M, and 100M storage/deployment discussions as estimates. Local results are dependent on hardware, Docker resource limits, image versions, index state, and database warm-up. Repeat runs on the target deployment with production-like data and concurrency before choosing a system.

## Test and report commands

```powershell
python -m unittest discover -s tests -v
python -m py_compile generate_threats.py mongo_operations.py cassandra_operations.py neo4j_operations.py benchmark.py run_all.py generate_report.py
python generate_report.py
```

## Docker Hub publication

Build/tag after authenticating with Docker Desktop or `docker login` in a terminal:

```powershell
docker build -t raja6303/mongodb-exercise18:latest .
docker push raja6303/mongodb-exercise18:latest
```

The image is published at https://hub.docker.com/r/raja6303/mongodb-exercise18 with the `latest` tag. The push was verified on 2026-11-15 with digest `sha256:a37fcc7a1a8e81a301ce443b88ba7f1c2cf9f55d1589d7890f1fcb02462333ee`. No credentials are stored in this repository.

## Student details

Edit the cover-page placeholders in the generated PDF workflow by updating the relevant values in `generate_report.py`: student, course/section, instructor, and submission date.
