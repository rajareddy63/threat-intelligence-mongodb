"""Lab 8.1 - Deploy a Local Replica Set (3 data-bearing members).

What this script does
  1. docker compose up -d   -> starts 3 MongoDB containers
  2. mongosh --file         -> initialises replica set rs0 (lab_8_1_init_replicaset.js)
  3. PyMongo                -> reads rs.status(): primary, secondaries, health
  4. PyMongo                -> inserts on the primary, proves it appears on both secondaries

Run:  python lab_8_1_deploy_replicaset.py
Needs: Docker Desktop running, `pip install pymongo`.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime

from pymongo import MongoClient
from pymongo.errors import PyMongoError

HERE = os.path.dirname(os.path.abspath(__file__))
COMPOSE_FILE = os.path.join(HERE, "docker-compose.yml")
PROJECT = "mongo-rs-lab"          # same project name in every activity folder
RS_NAME = "rs0"
# Members talk to each other by CONTAINER NAME on Docker's private network
# (e.g. mongo-rs0-1:27017).  Every container listens on 27017 inside Docker;
# Docker publishes them on localhost:27017 / 27018 / 27019 for this script.


# ----------------------------------------------------------------- helpers
def banner(text):
    line = "=" * 66
    print(f"\n{line}\n  {text}\n{line}")


def step(text):
    print(f"\n--- {text} ---")


def require_docker():
    if shutil.which("docker") is None:
        sys.exit("[ERROR] Docker is not on PATH. Install / start Docker Desktop.")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        sys.exit("[ERROR] Docker daemon is not running. Start Docker Desktop and retry.")


def compose(*args):
    """Run docker compose (v2) or docker-compose (v1) on this folder's file."""
    if subprocess.run(["docker", "compose", "version"],
                      capture_output=True).returncode == 0:
        base = ["docker", "compose"]
    elif shutil.which("docker-compose"):
        base = ["docker-compose"]
    else:
        sys.exit("[ERROR] Docker Compose not found.")
    cmd = base + ["-p", PROJECT, "-f", COMPOSE_FILE] + list(args)
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def direct(port, timeout_ms=3000):
    """Connect to ONE specific member (no replica-set discovery)."""
    return MongoClient("localhost", port, directConnection=True,
                       serverSelectionTimeoutMS=timeout_ms)


def port_in_use(port):
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def check_ports_free(ports, wait=8):
    """Stop early (with a clear message) if another program already uses a port."""
    deadline = time.time() + wait
    while True:
        busy = [p for p in ports if port_in_use(p)]
        if not busy:
            return
        if time.time() > deadline:
            sys.exit("[ERROR] Port(s) %s on this PC are already in use by another program,\n"
                     "        so the Docker containers cannot use them. Close that program\n"
                     "        (find it with:  netstat -ano | findstr :%d ) and run again."
                     % (", ".join(map(str, busy)), busy[0]))
        time.sleep(1)


def wait_for_mongod(ports, timeout=90):
    deadline = time.time() + timeout
    for p in ports:
        while True:
            try:
                cl = direct(p, 1500)
                cl.admin.command("ping")
                argv = cl.admin.command("getCmdLineOpts").get("argv", [])
                if "--replSet" not in argv:
                    sys.exit(f"[ERROR] localhost:{p} answers, but it is NOT one of this lab's "
                             "Docker containers\n        (another MongoDB is using that port). "
                             "Stop it or free the port, then run again.")
                print(f"  [OK] lab container on localhost:{p} is up")
                break
            except PyMongoError:
                if time.time() > deadline:
                    sys.exit(f"[ERROR] mongod on port {p} did not start in time.")
                time.sleep(1)


def run_mongosh_file(port, js_name, env=None):
    """Copy a .js file into the container and execute it with mongosh --file.

    `env` values are passed to the script by prepending `var KEY_ARG = "value";`
    to a temporary copy (the original .js file is not modified)."""
    import json
    import tempfile
    container = NODES[port]
    js_path = os.path.join(HERE, js_name)
    remote = f"/tmp/{js_name}"
    with open(js_path, encoding="utf-8") as f:
        code = f.read()
    prelude = "".join(f"var {k}_ARG = {json.dumps(v)};\n" for k, v in (env or {}).items())
    with tempfile.TemporaryDirectory() as tmp:
        tmp_js = os.path.join(tmp, js_name)
        with open(tmp_js, "w", encoding="utf-8") as f:
            f.write(prelude + code)
        subprocess.run(["docker", "cp", tmp_js, f"{container}:{remote}"], check=True)
    cmd = ["docker", "exec", container, "mongosh", "--quiet",
           "--port", "27017", "--file", remote]
    print(f"$ mongosh --file {js_name}   (inside {container})")
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout + r.stderr).rstrip()
    print(out)
    return out


def get_status():
    """replSetGetStatus from the first reachable member (None if not initiated)."""
    for p in NODES:
        try:
            return direct(p, 1500).admin.command("replSetGetStatus")
        except PyMongoError:
            continue
    return None


def split_host(name):
    """'mongo-rs0-2:27017' -> ('mongo-rs0-2', 27018)  (port = the localhost port)."""
    host = name.rsplit(":", 1)[0]
    for port, container in NODES.items():
        if container == host:
            return host, port
    return host, int(name.rsplit(":", 1)[1])


def primary_port(status):
    for m in status["members"]:
        if m["stateStr"] == "PRIMARY":
            return split_host(m["name"])[1]
    return None


def wait_for_primary(timeout=60, not_port=None):
    """Poll until a PRIMARY exists (optionally one different from not_port)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = get_status()
        if st:
            p = primary_port(st)
            if p and p != not_port:
                return p
        time.sleep(0.5)
    return None


def print_status(status):
    print(f"  {'MEMBER':<30}{'STATE':<26}{'HEALTH':<8}")
    for m in sorted(status["members"], key=lambda x: x["_id"]):
        health = "1 (up)" if m["health"] == 1 else "0 (down)"
        print(f"  {m['name']:<30}{m['stateStr']:<26}{health:<8}")


# ---------------------------------------------------------------- lab code
from pymongo import ReadPreference
from datetime import timezone

NODES = {28017: "mongo-rs0-1", 28018: "mongo-rs0-2", 28019: "mongo-rs0-3"}
JS_FILE = "lab_8_1_init_replicaset.js"


def main():
    banner("Lab 8.1 - Deploy a Local 3-Node Replica Set")
    require_docker()

    # Step 1 -------------------------------------------------------------
    step("Step 1: Start 3 MongoDB containers with Docker Compose")
    compose("down", "-v", "--remove-orphans")     # clean slate
    check_ports_free(NODES.keys())
    compose("up", "-d")
    wait_for_mongod(NODES.keys())

    # Step 2 -------------------------------------------------------------
    step("Step 2: Initialise the replica set with mongosh")
    run_mongosh_file(28017, JS_FILE)

    # Step 3 -------------------------------------------------------------
    step("Step 3: Wait for the primary and read rs.status() through PyMongo")
    p_port = wait_for_primary()
    if p_port is None:
        sys.exit("[ERROR] No primary was elected.")
    status = get_status()
    print_status(status)
    secondaries = [split_host(m["name"])[1] for m in status["members"]
                   if m["stateStr"] == "SECONDARY"]
    print(f"\n  PRIMARY     : localhost:{p_port}")
    print(f"  SECONDARIES : {', '.join('localhost:%d' % s for s in secondaries)}")

    # Step 4 -------------------------------------------------------------
    step("Step 4: Insert on the PRIMARY and verify it appears on both SECONDARIES")
    doc = {"message": "Hello from replica set!", "lab": "8.1",
           "inserted_at": datetime.now(timezone.utc)}
    t0 = time.perf_counter()
    res = direct(p_port).labdb.replication_test.insert_one(doc)   # w:1 on purpose
    print(f"  Inserted _id={res.inserted_id} on PRIMARY localhost:{p_port}")

    print("\n  (a) PyMongo read from each secondary:")
    for s in secondaries:
        sc = MongoClient("localhost", s, directConnection=True,
                         serverSelectionTimeoutMS=3000,
                         read_preference=ReadPreference.SECONDARY_PREFERRED)
        found, last_err = None, None
        t1 = time.perf_counter()
        while time.perf_counter() - t1 < 20:
            try:
                found = sc.labdb.replication_test.find_one({"_id": res.inserted_id})
            except PyMongoError as e:
                last_err = e
            if found:
                break
            time.sleep(0.2)
        if found:
            print(f"    [OK] localhost:{s} has the document "
                  f"(visible after ~{(time.perf_counter() - t0) * 1000:.0f} ms): "
                  f"{found['message']!r}")
        else:
            print(f"    [no result] localhost:{s}  last error: {last_err}")
        sc.close()

    print("\n  (b) mongosh cross-check: count of documents on EVERY member")
    all_ok = True
    for port, container in NODES.items():
        r = subprocess.run(
            ["docker", "exec", container, "mongosh", "--quiet", "--port", "27017",
             "--eval",
             "db.getMongo().setReadPref('secondaryPreferred');"
             "print('COUNT=' + db.getSiblingDB('labdb').replication_test.countDocuments({}))"],
            capture_output=True, text=True)
        text = (r.stdout + r.stderr).strip()
        count = text.split("COUNT=")[-1].split()[0] if "COUNT=" in text else None
        role = "PRIMARY  " if port == p_port else "SECONDARY"
        if count is not None and int(count) >= 1:
            print(f"    [OK] {container}  {role}  labdb.replication_test has {count} document(s)")
        else:
            all_ok = False
            print(f"    [FAIL] {container}  {role}  -> {text[:200]}")

    # Step 5 -------------------------------------------------------------
    step("Step 5: Final rs.status() health check")
    print_status(get_status())
    banner("Lab 8.1 PASSED - replication verified" if all_ok else "Lab 8.1 FAILED")
    print("Leave the containers running for Lab 8.2.  Stop later with:")
    print(f"  docker compose -p {PROJECT} -f docker-compose.yml down -v")


if __name__ == "__main__":
    main()
