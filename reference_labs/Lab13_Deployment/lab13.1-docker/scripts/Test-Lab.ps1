param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Push-Location $ProjectRoot
try {
    docker compose ps
    if ($LASTEXITCODE -ne 0) { throw 'Could not query Docker Compose. Is Docker Desktop running?' }
    docker compose --profile init run --rm replica-set-init
    if ($LASTEXITCODE -ne 0) { throw 'Replica-set initialization or health verification failed.' }
    docker compose run --rm client status
    if ($LASTEXITCODE -ne 0) { throw 'Replica-set status check failed.' }
    docker compose run --rm client write-read
    if ($LASTEXITCODE -ne 0) { throw 'PyMongo write/read check failed.' }
    Write-Output 'Optional controlled failover: docker compose run --rm client failover'
    Write-Output 'Optional metrics: docker compose --profile monitoring up -d; open http://localhost:9090'
}
finally {
    Pop-Location
}
