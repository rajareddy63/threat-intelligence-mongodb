# Exercise 16 - Hybrid Databases

This project implements the required data modeling and fraud analysis workflow for Exercise 16 across MongoDB, Cassandra, and Neo4j.

## Structure

- `lab16.1-data-modeling/` - model design and query examples for MongoDB, Cassandra, and Neo4j.
- `lab16.2-hybrid-service/` - Python service implementing a hybrid fraud query workflow.
- `docker/` - Docker Compose and image definition.
- `scripts/` - PowerShell helpers for start, test, stop, and initialization.
- `reports/` - final generated PDF and supporting artifacts.

## Validation status

- Unit and integration tests pass under Python 3.11 using the project’s supported Cassandra stack.
- Verified local Docker services: MongoDB, Cassandra, and Neo4j are running healthy.
- Actual latency measurements are captured in `latency_results.csv`.
- Final report PDF is generated under `reports/Exercise16_Hybrid_Database_Report.pdf`.

## Runtime note

The repository intentionally targets Python 3.11 for validation because the Cassandra Python driver and eventlet stack are not stable on Python 3.12 in this environment.
