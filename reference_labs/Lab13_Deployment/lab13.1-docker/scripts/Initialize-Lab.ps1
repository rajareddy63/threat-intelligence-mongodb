param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path $ProjectRoot 'secrets'
$keyFile = Join-Path $secretDirectory 'keyfile'
$envFile = Join-Path $ProjectRoot '.env'

New-Item -ItemType Directory -Force -Path $secretDirectory | Out-Null

if (-not (Test-Path -LiteralPath $keyFile)) {
    $keyBytes = New-Object byte[] 756
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($keyBytes) } finally { $random.Dispose() }
    $key = [Convert]::ToBase64String($keyBytes)
    [IO.File]::WriteAllText($keyFile, $key, [Text.Encoding]::ASCII)
}

if (-not (Test-Path -LiteralPath $envFile)) {
    $passwordBytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($passwordBytes) } finally { $random.Dispose() }
    $password = ([BitConverter]::ToString($passwordBytes)).Replace('-', '').ToLowerInvariant()
    $exporterPasswordBytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($exporterPasswordBytes) } finally { $random.Dispose() }
    $exporterPassword = ([BitConverter]::ToString($exporterPasswordBytes)).Replace('-', '').ToLowerInvariant()
    @(
        'MONGO_ROOT_USERNAME=labadmin'
        "MONGO_ROOT_PASSWORD=$password"
        'MONGO_EXPORTER_USERNAME=mongo_exporter'
        "MONGO_EXPORTER_PASSWORD=$exporterPassword"
        'MONGO_EXPORTER_VERSION=0.44.0'
        'MONGO1_HOST_PORT=37017'
        'MONGO2_HOST_PORT=37018'
        'MONGO3_HOST_PORT=37019'
    ) | Set-Content -LiteralPath $envFile -Encoding ascii
}

Write-Output 'Generated the replica-set keyfile and local credentials if they did not already exist.'
Write-Output 'Secrets remain in ignored local files; do not commit them.'
Write-Output 'Next: docker compose up -d mongo1 mongo2 mongo3'
