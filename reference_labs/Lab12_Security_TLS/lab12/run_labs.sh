#!/bin/bash
# Runs the full demonstration for Lab 12.1 and Lab 12.2
cd /lab
echo "################ LAB 12.1 : Auth + RBAC + redaction view ################"
python3 -I lab12_1_test.py
echo
echo "---- mongosh: unauthorized attempt ----"
mongosh --quiet --port 27017 -u app_user_read -p "$READ_PWD" --authenticationDatabase admin \
  --eval 'try { db.getSiblingDB("company").employees.find().toArray() } catch(e) { print("ERROR:", e.message) }'
echo
echo "################ LAB 12.2 : TLS in transit ################"
echo "---- plain mongosh to TLS port (expected failure) ----"
timeout 15 mongosh --quiet --port 27018 --eval 'db.runCommand({ping:1})' 2>&1 | tail -2
echo "---- mongosh with TLS ----"
mongosh --quiet --port 27018 --tls --tlsCAFile certs/ca.crt --tlsCertificateKeyFile certs/client.pem \
  -u admin -p "$ADMIN_PWD" --authenticationDatabase admin --eval 'printjson(db.runCommand({ping:1}))'
python3 -I lab12_2_test.py
echo
echo "---- programmatic cert generation (cryptography) ----"
python3 -I gen_certs.py /tmp/certs_py && ls /tmp/certs_py
