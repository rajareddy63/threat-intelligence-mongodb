import time
from pymongo import MongoClient

URI = "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0"
N = 1000
levels = [("w:1", 1), ("w:majority", "majority"), ("w:3 (all)", 3)]

print(f"{'Concern':<12}{'journal':<9}{'total (s)':<11}{'avg (ms)':<10}")
for j in (False, True):
    for name, w in levels:
        c = MongoClient(URI, w=w, journal=j, wtimeoutMS=10000)
        col = c.lab9.writes
        col.drop()
        t0 = time.perf_counter()
        for i in range(N):
            col.insert_one({"i": i, "payload": "x" * 50})
        total = time.perf_counter() - t0
        print(f"{name:<12}{str(j):<9}{total:<11.2f}{total / N * 1000:<10.2f}")
        c.close()
