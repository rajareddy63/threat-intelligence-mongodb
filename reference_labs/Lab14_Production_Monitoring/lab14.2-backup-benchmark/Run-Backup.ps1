param(
    [switch]$Schedule
)

$ErrorActionPreference = 'Stop'
$composeFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'lab14.1-docker\docker-compose.yml'

if ($Schedule) {
    docker compose -f $composeFile --profile backup up -d backup-scheduler
}
else {
    docker compose -f $composeFile --profile backup run --rm backup-scheduler bash /scripts/backup.sh
}

if ($LASTEXITCODE -ne 0) {
    throw "Backup command failed with exit code $LASTEXITCODE"
}
