$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\.. 
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is required." }
docker compose -f docker\docker-compose.yml up -d --build
Write-Host "Docker environment started."
