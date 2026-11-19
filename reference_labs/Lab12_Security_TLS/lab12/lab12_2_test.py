#!/usr/bin/env python3
"""Lab 12.2 - verify TLS-only mongod on :27018."""
import os, subprocess
from pymongo import MongoClient
from pymongo.errors import PyMongoError

C = "/lab/certs"
pw = os.environ["ADMIN_PWD"]
fails = 0

# 1. Plain (non-TLS) connection must be rejected
try:
    MongoClient("mongodb://admin:%s@localhost:27018/?authSource=admin" % pw,
                serverSelectionTimeoutMS=3000).admin.command("ping")
    print("[FAIL] unencrypted connection was accepted"); fails += 1
except PyMongoError as e:
    print("[PASS] unencrypted connection rejected:", type(e).__name__)

# 2. TLS connection with CA + client cert succeeds; run find_one
uri = (f"mongodb://admin:{pw}@localhost:27018/?authSource=admin&tls=true"
       f"&tlsCAFile={C}/ca.crt&tlsCertificateKeyFile={C}/client.pem")
c = MongoClient(uri, serverSelectionTimeoutMS=5000)
c.test.test.delete_many({}); c.test.test.insert_one({"msg": "hello over TLS"})
doc = c.test.test.find_one({}, {"_id": 0})
print("[PASS] TLS find_one:", doc); fails += 0 if doc else 1

# 3. TLS with wrong/no CA must fail verification
try:
    MongoClient(f"mongodb://admin:{pw}@localhost:27018/?authSource=admin&tls=true",
                serverSelectionTimeoutMS=3000).admin.command("ping")
    print("[FAIL] untrusted CA accepted"); fails += 1
except PyMongoError as e:
    print("[PASS] connection without trusted CA rejected:", type(e).__name__)

# 4. Document certificate chain
print("\n== Certificate chain ==")
print(subprocess.run(["openssl", "verify", "-CAfile", f"{C}/ca.crt", f"{C}/server.crt", f"{C}/client.crt"],
                     capture_output=True, text=True).stdout)
for n in ("ca", "server", "client"):
    print(subprocess.run(["openssl", "x509", "-in", f"{C}/{n}.crt", "-noout", "-subject", "-issuer"],
                         capture_output=True, text=True).stdout.strip())

print("\nRESULT:", "ALL CHECKS PASSED" if fails == 0 else f"{fails} FAILED")
raise SystemExit(fails)
