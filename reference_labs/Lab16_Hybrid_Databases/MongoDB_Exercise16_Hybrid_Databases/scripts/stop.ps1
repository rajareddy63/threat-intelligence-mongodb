$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\.. 
docker compose -f docker\docker-compose.yml down
Write-Host "Docker environment stopped."
