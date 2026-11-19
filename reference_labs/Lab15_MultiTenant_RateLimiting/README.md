# Chapter 15 - MongoDB Multi-Tenant SaaS Labs

Lab 15.1: Multi-Tenant Task API and Rate Limiting

Lab 15.2: Tenant Data Migration and Rollback

Name: G RAJA SIMHA REDDY

USN: 24BTRCL070

Docker Hub URL: https://hub.docker.com/r/raja6303/exercise15-multitenant

Docker image: raja6303/exercise15-multitenant:latest

Pull image: `docker pull raja6303/exercise15-multitenant:latest`

## Lab 15.1 - Multi-Tenant API

The task API uses one shared MongoDB collection and a `tenant_id` field to
separate customer data. Task listing filters on the tenant. Task updates use
both the task ID and tenant ID, so a tenant cannot update another tenant's
record by supplying its ID.

The API also enforces a per-tenant request limit using atomic MongoDB counters
with a fixed time window.

Run the demonstration with MongoDB available:

```sh
docker run --rm -e MONGODB_URI=mongodb://host.docker.internal:27017 raja6303/exercise15-multitenant:latest
```

The demo creates sample tasks for two tenants, verifies that a cross-tenant
update is rejected, and displays the rate-limit decisions.

## Lab 15.2 - Tenant Migration

The migration copies one tenant's task records from `saas_app.tasks` into that
tenant's dedicated database. It supports a dry run, repeatable upsert migration
using `task_key`, and rollback that drops only the dedicated database. The
shared source documents are preserved.

Run a dry run, perform the migration, then roll back if required:

```sh
docker run --rm -e MONGODB_URI=mongodb://host.docker.internal:27017 raja6303/exercise15-multitenant:latest lab_02_tenant_migration.py --tenant customer-42 --dry-run
docker run --rm -e MONGODB_URI=mongodb://host.docker.internal:27017 raja6303/exercise15-multitenant:latest lab_02_tenant_migration.py --tenant customer-42
docker run --rm -e MONGODB_URI=mongodb://host.docker.internal:27017 raja6303/exercise15-multitenant:latest lab_02_tenant_migration.py --tenant customer-42 --rollback
```

## Verification

The Docker image built successfully and was pushed to Docker Hub. All 7 unit
tests passed, including tenant-scoped updates, per-tenant rate limits, dry-run
behavior, migration repeatability, missing migration-key validation, and
rollback targeting.

Unit tests use mocked MongoDB collections and do not require a live database.
The demonstration and migration commands require a MongoDB server.
