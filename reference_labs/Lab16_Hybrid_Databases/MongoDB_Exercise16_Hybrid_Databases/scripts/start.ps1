$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\.. 
docker compose -f docker\docker-compose.yml up -d
Write-Host "Services are running."
