$ErrorActionPreference = 'Stop'

$labRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $labRoot 'docker-compose.yml'

if (Test-Path $composeFile) {
    docker compose -f $composeFile down -v --remove-orphans
}

Get-ChildItem -Path (Join-Path $labRoot 'data') -Recurse -Directory -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Force -Path (Join-Path $labRoot 'secrets\keyfile') -ErrorAction SilentlyContinue

Write-Host 'MongoDB lab reset complete.'
