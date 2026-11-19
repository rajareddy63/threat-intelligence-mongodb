"""Lab 8.2 - Observe Failover and Election.

  1. rs.stepDown() through mongosh (lab_8_2_stepdown.js) and watch the election
  2. rs.status() afterwards to identify the new primary
  3. A reader thread continuously reads from the replica set and logs WHICH member
     answered; a 2nd stepDown is forced and the reconnection is observed.

Run:  python lab_8_2_failover_observer.py
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
import threading

NODES = {28017: "mongo-rs0-1", 28018: "mongo-rs0-2", 28019: "mongo-rs0-3"}
JS_FILE = "lab_8_2_stepdown.js"

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def now():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


# ------------------------------------------------------------ deployment
def ensure_replica_set():
    """Re-use the Lab 8.1 replica set if it is still running, else deploy it."""
    st = get_status()
    if st and primary_port(st) and len(st["members"]) == 3 \
            and all(m["stateStr"] != "ARBITER" for m in st["members"]):
        print("  Re-using the replica set that is already running (Lab 8.1).")
        return
    print("  No suitable replica set found - deploying a fresh one.")
    compose("down", "-v", "--remove-orphans")
    check_ports_free(NODES.keys())
    compose("up", "-d")
    wait_for_mongod(NODES.keys())
    cfg = {"_id": RS_NAME,
           "members": [{"_id": i, "host": f"{name}:27017"}
                       for i, name in enumerate(NODES.values())]}
    direct(28017).admin.command("replSetInitiate", cfg)
    if wait_for_primary() is None:
        sys.exit("[ERROR] No primary was elected.")


# --------------------------------------------------------- the reader thread
class Reader(threading.Thread):
    """Continuously reads from the replica set and logs WHICH member answered.

    Docker's member names (mongo-rs0-1 ...) cannot be resolved from Windows, so
    instead of one replicaSet=rs0 client the reader keeps one direct connection
    per member and always reads from whichever member currently reports
    isWritablePrimary - the same job a replica-set aware driver does."""

    def __init__(self, interval=0.2):
        super().__init__(daemon=True)
        self.interval = interval
        self.stop_event = threading.Event()
        self.events = []            # (time, text) for the final summary
        self.gaps = []              # seconds without a reachable primary

    def run(self):
        clients = {p: MongoClient("localhost", p, directConnection=True,
                                  serverSelectionTimeoutMS=800,
                                  connectTimeoutMS=800, socketTimeoutMS=1500)
                   for p in NODES}
        last_member, down_since, n = None, None, 0
        while not self.stop_event.is_set():
            n += 1
            t0 = time.time()
            member, doc = None, None
            for port, c in clients.items():
                try:
                    if c.admin.command("hello").get("isWritablePrimary"):
                        member = f"{NODES[port]} (localhost:{port})"
                        doc = c.labdb.failover_reads.find_one({"_id": "seed"})
                        break
                except PyMongoError:
                    continue
            if member is None:
                if down_since is None:
                    down_since = t0
                    self.events.append((now(), "lost the primary"))
                log(f"  [{now()}] read #{n:<3} !! NO PRIMARY AVAILABLE (election in progress)")
            else:
                ms = (time.time() - t0) * 1000
                mark = ""
                if down_since is not None:
                    gap = time.time() - down_since
                    self.gaps.append(gap)
                    mark = f"  <-- RECONNECTED after {gap:.1f}s without a primary"
                    self.events.append((now(), f"reconnected to {member} after {gap:.1f}s"))
                    down_since = None
                if member != last_member:
                    if last_member is not None:
                        mark += f"  <-- NOW CONNECTED TO NEW PRIMARY (was {last_member})"
                        self.events.append((now(), f"primary changed: {last_member} -> {member}"))
                    last_member = member
                log(f"  [{now()}] read #{n:<3} member={member:<34} "
                    f"doc={'ok' if doc else 'missing'} ({ms:4.0f} ms){mark}")
            self.stop_event.wait(self.interval)
        for c in clients.values():
            c.close()


def force_step_down(label):
    st = get_status()
    p = primary_port(st)
    log(f"\n>>> [{now()}] {label}: running rs.stepDown() on localhost:{p}")
    out = run_mongosh_file(p, JS_FILE)
    return out


def main():
    banner("Lab 8.2 - Observe Failover and Election")
    require_docker()

    step("Step 0: Make sure the 3-node replica set is running")
    ensure_replica_set()
    print_status(get_status())

    # Seed one document so the reader has something to read
    p = primary_port(get_status())
    from pymongo import WriteConcern
    direct(p).labdb.failover_reads.with_options(
        write_concern=WriteConcern("majority")
    ).replace_one({"_id": "seed"}, {"_id": "seed", "msg": "hello"}, upsert=True)

    # ---------------------------------------------------------------- 1 + 2
    step("Steps 1-2: rs.stepDown() with the mongosh file, then identify new primary")
    old = primary_port(get_status())
    run_mongosh_file(old, JS_FILE)
    new = wait_for_primary(not_port=old, timeout=30) or primary_port(get_status())
    print(f"\n  Python check: primary moved localhost:{old} -> localhost:{new}")
    print_status(get_status())

    # ------------------------------------------------------------------ 3
    step("Step 3: Continuous reader + second forced stepDown")
    print("  Waiting 35 s so the first stepDown freeze period (30 s) expires...")
    time.sleep(35)

    reader = Reader()
    reader.start()
    time.sleep(6)                                # let the reader log a few reads
    force_step_down("STEP-DOWN #2")
    wait_for_primary(not_port=None, timeout=30)
    time.sleep(8)                                # keep reading on the new primary
    reader.stop_event.set()
    reader.join(timeout=5)

    # --------------------------------------------------------------- summary
    step("Summary")
    for t, text in reader.events:
        print(f"  [{t}] {text}")
    if reader.gaps:
        print(f"\n  Longest period with NO primary (writes impossible): "
              f"{max(reader.gaps):.1f} s")
    else:
        print("\n  No read failed: the election finished between two consecutive reads"
              " (well under 1 s).")
    print("\n  Final replica set state:")
    print_status(get_status())
    banner("Lab 8.2 complete")


if __name__ == "__main__":
    main()
