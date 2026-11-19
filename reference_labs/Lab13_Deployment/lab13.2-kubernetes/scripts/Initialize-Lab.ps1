param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$dockerLab = Join-Path (Split-Path -Parent $ProjectRoot) 'lab13.1-docker'
$secrets = Join-Path $dockerLab 'secrets'
$envFile = Join-Path $dockerLab '.env'
$keyFile = Join-Path $secrets 'keyfile'

if (-not (Test-Path -LiteralPath $keyFile) -or -not (Test-Path -LiteralPath $envFile)) {
    & (Join-Path $dockerLab 'scripts\Initialize-Lab.ps1') -ProjectRoot $dockerLab
}

$envValues = @{}
Get-Content -LiteralPath $envFile | ForEach-Object {
    $parts = $_ -split '=', 2
    if ($parts.Length -eq 2) { $envValues[$parts[0]] = $parts[1] }
}

kubectl create namespace mongo-lab --dry-run=client -o yaml | kubectl apply -f -
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the Kubernetes namespace. Check the current kubectl context.' }
$usernameFile = Join-Path $secrets 'k8s-username'
$passwordFile = Join-Path $secrets 'k8s-password'
try {
    [IO.File]::WriteAllText($usernameFile, $envValues['MONGO_ROOT_USERNAME'], [Text.Encoding]::ASCII)
    [IO.File]::WriteAllText($passwordFile, $envValues['MONGO_ROOT_PASSWORD'], [Text.Encoding]::ASCII)
    kubectl -n mongo-lab create secret generic mongo-auth `
        --from-file=username=$usernameFile `
        --from-file=password=$passwordFile `
        --dry-run=client -o yaml | kubectl apply -f -
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Kubernetes MongoDB auth Secret.' }
    kubectl -n mongo-lab create secret generic mongo-keyfile `
        --from-file=keyfile=$keyFile `
        --dry-run=client -o yaml | kubectl apply -f -
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Kubernetes keyfile Secret.' }
    Write-Output 'Created/updated namespace and Kubernetes Secrets without printing secret contents.'
}
finally {
    Remove-Item -LiteralPath $usernameFile, $passwordFile -Force -ErrorAction SilentlyContinue
}
