# Exercise 13 — MongoDB deployment

Standalone college-lab project for Docker Compose, Kubernetes StatefulSet, and an optional MongoDB Atlas M0 Terraform configuration.

## Status on this machine

- Docker Desktop is running. The three-node Compose replica set is healthy; PyMongo read/write, controlled primary failover, and Prometheus monitoring tests passed.
- Docker Hub image `raja6303/mongodb-lab13-demo:1.0.0` was pushed with approval and verified by remote manifest. Repository: https://hub.docker.com/r/raja6303/mongodb-lab13-demo
- `kubectl` is installed, but no Kubernetes context is configured. Manifests pass static schema validation; Kubernetes deployment and runtime resiliency remain untested.
- Terraform format, initialization, and validation passed in Terraform 1.9.8. No Atlas plan/apply was run and no cloud resources were created.
- The PDF reports actual test outcomes and distinguishes untested Kubernetes runtime behavior from successful manifest validation.

## Deliverables

- `lab13.1-docker/`: compose services, generated-local-secret workflow, MongoDB keyfile authentication, initialization, PyMongo read/write/failover client, and optional Prometheus exporter.
- `lab13.2-kubernetes/`: headless service, StatefulSet with persistent claims/keyfile init container/probes, and guarded PowerShell scripts.
- `terraform/`: Atlas M0 project/cluster/database user with a restricted CIDR access list.
- `reports/Exercise_13_MongoDB_Deployment_Report.pdf`: formatted report.
- `screenshots/`: genuine Docker deployment evidence is captured when available; Kubernetes screenshots require a configured local cluster.

## Start the Docker lab when Docker Desktop is running

```powershell
cd C:\Users\rajar\Downloads\MongoDB_Exercise13_Deployment\lab13.1-docker
.\scripts\Initialize-Lab.ps1
docker compose up -d mongo1 mongo2 mongo3
docker compose --profile init run --rm replica-set-init
docker compose run --rm client write-read
docker compose run --rm client failover
docker compose --profile monitoring up -d
```

On this machine PowerShell's default execution policy is `Restricted`. To run the included local scripts, set `RemoteSigned` for the current PowerShell process only; that setting resets when the window closes. Do not lower machine-wide policy for this exercise.

Image tag: `raja6303/mongodb-lab13-demo:1.0.0`. MongoDB is published on loopback ports 37017–37019 to avoid the existing host `mongod` on 27017.
