import subprocess, time
from pymongo import MongoClient, WriteConcern
from pymongo.errors import PyMongoError

URI = "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0"

def sh(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def container_for(service):
    return sh(f"docker ps -a --format '{{{{.Names}}}}' | grep -E '(^|-){service}(-|$)' | head -1")

NET = sh("docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' "
         + container_for("mongo1"))
now = lambda: time.strftime("%H:%M:%S")

def status():
    try:
        c = MongoClient(URI, serverSelectionTimeoutMS=4000, directConnection=False)
        s = c.admin.command("replSetGetStatus")
        print(f"[{now()}]  members:", [(m["name"], m["stateStr"]) for m in s["members"]])
    except PyMongoError as e:
        print(f"[{now()}]  status unavailable ({type(e).__name__})")

def test(label):
    for name, w in (("w:1", 1), ("w:majority", "majority")):
        t0 = time.time()
        try:
            c = MongoClient(URI, serverSelectionTimeoutMS=5000)
            col = c.lab9.part.with_options(write_concern=WriteConcern(w=w, wtimeout=5000))
            col.insert_one({"phase": label, "wc": name})
            print(f"[{now()}]  {label} | {name}: OK ({time.time() - t0:.2f}s)")
        except PyMongoError as e:
            print(f"[{now()}]  {label} | {name}: FAILED - {type(e).__name__} ({time.time() - t0:.2f}s)")

def primary_service():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    return c.admin.command("hello")["primary"].split(":")[0]

prim = primary_service()
secs = [s for s in ("mongo1", "mongo2", "mongo3") if s != prim]
print(f"Primary is {prim}; secondaries are {secs}\n")

print("== Baseline ==");                      status(); test("baseline")

print(f"\n== Disconnecting {secs[0]} ==")
subprocess.run(["docker", "network", "disconnect", NET, container_for(secs[0])])
time.sleep(30);                              status(); test("1 secondary down")

print(f"\n== Disconnecting {secs[1]} (only primary left) ==")
subprocess.run(["docker", "network", "disconnect", NET, container_for(secs[1])])
time.sleep(20);                              status(); test("2 secondaries down")

print("\n== Reconnecting both ==")
for s in secs:
    subprocess.run(["docker", "network", "connect", "--alias", s, NET, container_for(s)])
time.sleep(30);                              status(); test("recovered")
print("\nDone. Copy this output into your report.")
