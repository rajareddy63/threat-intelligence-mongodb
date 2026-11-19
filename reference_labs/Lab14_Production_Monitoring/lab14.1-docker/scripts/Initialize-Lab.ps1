$ErrorActionPreference = 'Stop'

$labRoot = Split-Path -Parent $PSScriptRoot
$dotenv = Join-Path $labRoot '.env'
$secretPath = Join-Path $labRoot 'secrets\keyfile'
New-Item -ItemType Directory -Force -Path (Join-Path $labRoot 'secrets') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $labRoot 'logs') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $labRoot 'backups') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $labRoot 'results') | Out-Null

$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
if (-not (Test-Path $secretPath)) {
    $keyBytes = New-Object byte[] 512
    $rng.GetBytes($keyBytes)
    [System.IO.File]::WriteAllText($secretPath, [Convert]::ToBase64String($keyBytes))
}

if (-not (Test-Path $dotenv)) {
    $passwordBytes = New-Object byte[] 36
    $rng.GetBytes($passwordBytes)
    $password = [Convert]::ToBase64String($passwordBytes).TrimEnd('=').Replace('+', 'A').Replace('/', 'B')
    @(
        'MONGO_INITDB_ROOT_USERNAME=admin',
        "MONGO_INITDB_ROOT_PASSWORD=$password",
        'MONGO_PORT_1=37017',
        'MONGO_PORT_2=37018',
        'MONGO_PORT_3=37019',
        'APP_DATABASE=lab14',
        'APP_COLLECTION=orders',
        'DASHBOARD_PORT=8080',
        'MONITOR_INTERVAL_SECONDS=30',
        'CACHE_WARNING_PERCENT=80',
        'REPLICATION_LAG_WARNING_SECONDS=10',
        'ALERT_WEBHOOK_URL='
    ) | Set-Content -Path $dotenv
}
$rng.Dispose()

Write-Host 'Exercise 14 initialized. Start the replica set and dashboard with:'
Write-Host 'docker compose up -d --build'
Write-Host 'Local admin credentials are stored in the ignored .env file.'
