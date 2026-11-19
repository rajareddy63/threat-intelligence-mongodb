#!/usr/bin/env python3
"""Lab 12.2 - programmatic CA / server / client certificate generation (cryptography library)."""
import datetime, ipaddress, os, sys
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

OUT = sys.argv[1] if len(sys.argv) > 1 else "certs_py"
os.makedirs(OUT, exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc)


def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def build(subject_cn, subject_key, issuer_cn, issuer_key, ca=False, san=False, client=False):
    b = (x509.CertificateBuilder()
         .subject_name(name(subject_cn)).issuer_name(name(issuer_cn))
         .public_key(subject_key.public_key())
         .serial_number(x509.random_serial_number())
         .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=365))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if san:
        b = b.add_extension(x509.SubjectAlternativeName(
            [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
    if client:
        b = b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    return b.sign(issuer_key, hashes.SHA256())


def pem_key(k):
    return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                           serialization.NoEncryption())


def pem_cert(c):
    return c.public_bytes(serialization.Encoding.PEM)


def save(fname, data):
    with open(os.path.join(OUT, fname), "wb") as f:
        f.write(data)


ca_k = key(); ca_c = build("MongoDB-CA", ca_k, "MongoDB-CA", ca_k, ca=True)
srv_k = key(); srv_c = build("mongodb", srv_k, "MongoDB-CA", ca_k, san=True)
cli_k = key(); cli_c = build("pymongo-client", cli_k, "MongoDB-CA", ca_k, client=True)

save("ca.crt", pem_cert(ca_c))
save("server.pem", pem_key(srv_k) + pem_cert(srv_c))
save("client.pem", pem_key(cli_k) + pem_cert(cli_c))
print(f"Generated ca.crt, server.pem, client.pem in {OUT}/")
