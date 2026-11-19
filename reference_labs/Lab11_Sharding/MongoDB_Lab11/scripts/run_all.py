import os
import subprocess
import sys
import time
from pymongo import MongoClient

uri = os.getenv("MONGODB_URI", "mongodb://mongos:27017")
for attempt in range(30):
    try:
        MongoClient(uri, serverSelectionTimeoutMS=2000).admin.command("ping")
        break
    except Exception:
        if attempt == 29:
            raise
        print("Waiting for mongos...")
        time.sleep(2)

subprocess.check_call([sys.executable, "scripts/insert_data.py"])
subprocess.check_call([sys.executable, "scripts/analyze.py"])
