#!/bin/bash
set -euo pipefail
cd /lab
mkdir -p /data/boot /data/lab1 /data/lab2 /lab/logs

if [ ! -f /lab/certs/ca.crt ]; then
  echo ">> Generating TLS certificate chain"
  /lab/gen_certs.sh /lab/certs > /lab/logs/certs.log 2>&1
fi

if [ ! -f /data/.bootstrapped ]; then
  echo ">> Bootstrapping users/roles/view (temporary no-auth mongod)"
  mongod --dbpath /data/boot --bind_ip 127.0.0.1 --port 27099 --fork --logpath /lab/logs/boot.log >/dev/null
  mongosh --quiet --port 27099 /lab/setup.js
  mongod --dbpath /data/boot --shutdown >/dev/null
  cp -r /data/boot/. /data/lab1/
  cp -r /data/boot/. /data/lab2/
  touch /data/.bootstrapped
fi

echo ">> Lab 12.1 mongod: --auth on :27017 (no TLS)"
mongod --dbpath /data/lab1 --auth --bind_ip 127.0.0.1 --port 27017 --fork --logpath /lab/logs/lab1.log >/dev/null

echo ">> Lab 12.2 mongod: --auth + requireTLS on :27018"
mongod --dbpath /data/lab2 --auth --bind_ip 127.0.0.1 --port 27018 --fork --logpath /lab/logs/lab2.log \
  --tlsMode requireTLS --tlsCertificateKeyFile /lab/certs/server.pem --tlsCAFile /lab/certs/ca.crt \
  --tlsAllowConnectionsWithoutCertificates >/dev/null

echo ">> Ready. Run: /lab/run_labs.sh"
exec "$@"
