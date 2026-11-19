param(
    [string]$Namespace = 'mongo-lab'
)

$ErrorActionPreference = 'Stop'
$context = kubectl config current-context 2>$null
if (-not $context) { throw 'No Kubernetes context is configured; deployment/resiliency tests cannot run.' }
kubectl rollout status statefulset/mongo -n $Namespace --timeout=10m
if ($LASTEXITCODE -ne 0) { throw 'MongoDB StatefulSet rollout did not complete.' }
kubectl get pods,svc,pvc -n $Namespace -o wide
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect MongoDB StatefulSet resources.' }

kubectl wait --for=condition=complete job/mongo-replica-set-init -n $Namespace --timeout=10m
if ($LASTEXITCODE -ne 0) { throw 'The replica-set initialization Job is not complete.' }

$remoteStatusCommand = @'
mongosh "mongodb://${MONGO_INITDB_ROOT_USERNAME}:${MONGO_INITDB_ROOT_PASSWORD}@localhost:27017/admin?authSource=admin&directConnection=true" --quiet --eval '
  const members = rs.status().members;
  const primaryCount = members.filter(member => member.stateStr === "PRIMARY").length;
  const secondaryCount = members.filter(member => member.stateStr === "SECONDARY").length;
  if (members.length !== 3 || primaryCount !== 1 || secondaryCount !== 2) quit(1);
  printjson(members.map(member => ({name: member.name, state: member.stateStr})));
'
'@
$status = kubectl exec -n $Namespace mongo-0 -- sh -ec $remoteStatusCommand
if ($LASTEXITCODE -ne 0) { throw 'Replica-set status is not one primary and two secondaries before the resiliency test.' }
Write-Output 'Initial replica-set health:'
$status

$oldUid = kubectl get pod mongo-1 -n $Namespace -o jsonpath='{.metadata.uid}'
if ($LASTEXITCODE -ne 0 -or -not $oldUid) { throw 'Could not retrieve the mongo-1 pod UID.' }
Write-Output 'Deleting mongo-1 to test StatefulSet recreation; its persistent volume is preserved.'
kubectl delete pod mongo-1 -n $Namespace --wait=true
if ($LASTEXITCODE -ne 0) { throw 'Could not delete the mongo-1 pod for the controlled resiliency test.' }
kubectl wait --for=condition=Ready pod/mongo-1 -n $Namespace --timeout=5m
if ($LASTEXITCODE -ne 0) { throw 'The StatefulSet did not recreate mongo-1 within five minutes.' }
$newUid = kubectl get pod mongo-1 -n $Namespace -o jsonpath='{.metadata.uid}'
if ($LASTEXITCODE -ne 0 -or -not $newUid -or $newUid -eq $oldUid) {
    throw 'mongo-1 was not recreated with a new pod identity.'
}

$status = kubectl exec -n $Namespace mongo-0 -- sh -ec $remoteStatusCommand
if ($LASTEXITCODE -ne 0) { throw 'The recreated mongo-1 did not rejoin the three-member replica set.' }
Write-Output 'Replica-set health after pod recreation:'
$status
Write-Output "POD_RECOVERY_VERIFIED=True; previous UID=$oldUid; recreated UID=$newUid"
