$ErrorActionPreference = 'Stop'
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
docker compose ps
Write-Host 'Dashboard: http://localhost:8501'
Write-Host 'API docs:  http://localhost:8000/docs'
