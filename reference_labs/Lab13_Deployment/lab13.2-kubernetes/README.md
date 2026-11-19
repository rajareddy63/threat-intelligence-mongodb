# Lab 13.2 — MongoDB StatefulSet

`mongo-headless-svc.yaml` gives each StatefulSet member a predictable DNS identity: `mongo-0.mongo`, `mongo-1.mongo`, and `mongo-2.mongo` in namespace `mongo-lab`. `mongo-statefulset.yaml` requests one independent 5 GiB PVC per pod, mounts a Kubernetes Secret containing the keyfile, and uses an init container to stage the secret with MongoDB UID `999` and mode `0400`. Startup, readiness, and liveness probes are configured. `mongo-replica-set-init.yaml` automatically initiates the three-member `rs0` and waits for one primary and two secondaries. A default StorageClass and sufficient local cluster resources are required.

## Preconditions and deployment

Docker Desktop Kubernetes or another working Kubernetes installation, `kubectl`, a dynamic default StorageClass, and the secret-generation step are needed. Confirm the target context and inspect it before deployment:

```powershell
kubectl config get-contexts
kubectl config current-context
.\scripts\Deploy-Lab.ps1
kubectl rollout status statefulset/mongo -n mongo-lab --timeout=10m
kubectl get pods,svc,pvc -n mongo-lab -o wide
```

`Deploy-Lab.ps1` creates or updates the `mongo-lab` namespace and Secrets from the local ignored Docker-lab secrets, then applies the service, StatefulSet, and initialization Job. It refuses to continue when no context exists. Inspect the active context and ensure it is a disposable local lab before deploying.

## Replica-set initialization and recovery

The deployment script waits for the init Job, which authenticates using the Kubernetes Secret, uses the stable member DNS names, and verifies replica-set membership. The image's root initialization environment variables apply only on first initialization of each empty PVC. Verify each member with authenticated `rs.status()` and the generated credentials, and check PVC attachment before resetting anything.

To check Kubernetes rescheduling:

```powershell
kubectl delete pod mongo-1 -n mongo-lab
kubectl wait --for=condition=Ready pod/mongo-1 -n mongo-lab --timeout=5m
kubectl get pod mongo-1 -n mongo-lab -o wide
```

Then verify that `mongo-1.mongo:27017` has rejoined by querying the replica-set status from a MongoDB member. Do not delete the PVC. `.\scripts\Test-Lab.ps1` checks rollout/resources and replica-set health, deletes only `mongo-1` (never its PVC), waits for a new pod UID, then verifies that the member rejoins.

## Cleanup

After confirming the namespace and PVCs contain only disposable lab data, remove the StatefulSet/service manually. PVC deletion also deletes persistent data; it is intentionally excluded from automated scripts.
