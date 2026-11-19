#!/bin/bash
# Lab 12.2 - certificate chain via OpenSSL (CA -> server, CA -> client)
set -euo pipefail
D=${1:-/lab/certs}
mkdir -p "$D" && cd "$D"

# 1. CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 365 -key ca.key -out ca.crt -subj '/CN=MongoDB-CA'

# 2. Server key + CSR, signed by CA (SAN covers localhost / 127.0.0.1)
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj '/CN=mongodb'
openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -extfile <(echo 'subjectAltName=DNS:localhost,IP:127.0.0.1')
cat server.key server.crt > server.pem

# 3. Client key + CSR, signed by CA
openssl genrsa -out client.key 4096
openssl req -new -key client.key -out client.csr -subj '/CN=pymongo-client'
openssl x509 -req -days 365 -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out client.crt -extfile <(echo 'extendedKeyUsage=clientAuth')
cat client.key client.crt > client.pem

chmod 644 *.crt *.pem *.key
echo "== Certificate chain =="
for c in ca server client; do
  echo "--- $c.crt ---"; openssl x509 -in $c.crt -noout -subject -issuer -dates
done
openssl verify -CAfile ca.crt server.crt client.crt
