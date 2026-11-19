param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$context = kubectl config current-context 2>$null
if (-not $context) {
    throw 'No Kubernetes context is configured. Enable Kubernetes in Docker Desktop or configure a local cluster before deploying.'
}
Write-Output "Using Kubernetes context: $context"
& (Join-Path $PSScriptRoot 'Initialize-Lab.ps1') -ProjectRoot $ProjectRoot
kubectl apply -n mongo-lab -f (Join-Path $ProjectRoot 'mongo-headless-svc.yaml')
if ($LASTEXITCODE -ne 0) { throw 'Failed to apply the headless service.' }
kubectl apply -n mongo-lab -f (Join-Path $ProjectRoot 'mongo-statefulset.yaml')
if ($LASTEXITCODE -ne 0) { throw 'Failed to apply the StatefulSet.' }
kubectl apply -n mongo-lab -f (Join-Path $ProjectRoot 'mongo-replica-set-init.yaml')
if ($LASTEXITCODE -ne 0) { throw 'Failed to apply the replica-set initialization Job.' }
kubectl wait --for=condition=complete job/mongo-replica-set-init -n mongo-lab --timeout=10m
if ($LASTEXITCODE -ne 0) { throw 'MongoDB pods did not form a healthy three-member replica set.' }
Write-Output 'StatefulSet ready and replica-set initialization Job completed.'
