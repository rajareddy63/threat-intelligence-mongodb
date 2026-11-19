# MongoDB Lab 11.1 and 11.2

This project builds a local MongoDB 7.0 sharded cluster using Docker Compose.

## Requirements
- Docker Desktop with Docker Compose v2
- Internet connection for the first image pull
- Docker Hub account only when publishing the custom lab image

## 1. Start the cluster
Open PowerShell in this project folder and run:

```powershell
docker compose up -d configsvr shard1 shard2 mongos
```

Wait until the containers are healthy:

```powershell
docker compose ps
```

Initialize the replica sets and register both shards:

```powershell
docker compose run --rm init
```

## 2. Create the sharded collections

```powershell
docker compose exec mongos mongosh --eval "sh.status()"
```

Run the collection setup script from your computer:

```powershell
docker compose exec -T mongos mongosh < scripts/setup_collections.js
```

If PowerShell redirection causes a problem, use:

```powershell
Get-Content .\scripts\setup_collections.js | docker compose exec -T mongos mongosh
```

## 3. Build and run the lab scripts

```powershell
docker compose build lab
docker compose --profile lab run --rm lab
```

This inserts 10,000 documents into each collection and prints `collStats`, query explain plans, and shard information.

## 4. Inspect cluster status manually

```powershell
docker compose exec mongos mongosh
```

Then run in the MongoDB shell:

```javascript
sh.status()
db = db.getSiblingDB("lab11")
db.runCommand({ collStats: "hotspot_data" })
db.runCommand({ collStats: "even_data" })
```

## 5. Publish the custom lab image to Docker Hub

Create a repository on https://hub.docker.com/ (example: `mongodb-lab11`).

In PowerShell, replace `YOUR_DOCKERHUB_USERNAME` with your own Docker Hub username:

```powershell
docker login
docker build -t YOUR_DOCKERHUB_USERNAME/mongodb-lab11:1.0 .
docker push YOUR_DOCKERHUB_USERNAME/mongodb-lab11:1.0
```

The image contains the Python lab scripts. The MongoDB server images remain the official `mongo:7.0` images.

## 6. Stop the cluster

```powershell
docker compose down
```

To delete all database data and start fresh (this permanently removes the lab volumes):

```powershell
docker compose down -v
```

## Important notes
- Run setup only after the cluster is initialized.
- The collection setup script drops and recreates the two experiment collections. It is intended for a disposable lab.
- Shard counts are observations, not fixed targets. MongoDB version, chunk layout, and balancer timing affect the measured distribution.
- This is a local educational cluster with one member per replica set, not a production high-availability deployment.
