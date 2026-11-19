$ErrorActionPreference = 'Stop'
$composeFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'lab14.1-docker\docker-compose.yml'

docker compose -f $composeFile run --rm dashboard python app.py benchmark --counts 1000 10000 100000
if ($LASTEXITCODE -ne 0) {
    throw "Benchmark failed with exit code $LASTEXITCODE"
}
