import os
import sys
import time

from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure, OperationFailure, PyMongoError


def main() -> int:
    username = os.environ["MONGODB_ROOT_USERNAME"]
    password = os.environ["MONGODB_ROOT_PASSWORD"]
    exporter_username = os.environ["MONGODB_EXPORTER_USERNAME"]
    exporter_password = os.environ["MONGODB_EXPORTER_PASSWORD"]
    client = MongoClient(
        f"mongodb://{username}:{password}@mongo1:27017/admin?authSource=admin&directConnection=true",
        serverSelectionTimeoutMS=5000,
    )
    try:
        deadline = time.monotonic() + 180
        while True:
            try:
                client.admin.command("ping")
                break
            except (AutoReconnect, ConnectionFailure):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)

        config = {
            "_id": "rs0",
            "members": [
                {"_id": 0, "host": "mongo1:27017"},
                {"_id": 1, "host": "mongo2:27017"},
                {"_id": 2, "host": "mongo3:27017"},
            ],
        }
        try:
            client.admin.command("replSetInitiate", config)
            print("Initiated replica set rs0.")
        except OperationFailure as error:
            if error.code != 23:
                raise
            print("Replica set rs0 is already initialized.")

        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            status = client.admin.command("replSetGetStatus")
            states = {member["name"]: member["stateStr"] for member in status["members"]}
            print(f"Replica set member states: {states}")
            if (
                len(states) == 3
                and sum(state == "PRIMARY" for state in states.values()) == 1
                and sum(state == "SECONDARY" for state in states.values()) == 2
            ):
                replica_client = MongoClient(
                    f"mongodb://{username}:{password}@mongo1:27017,mongo2:27017,mongo3:27017/"
                    "?replicaSet=rs0&authSource=admin",
                    serverSelectionTimeoutMS=10000,
                )
                try:
                    replica_client.admin.command(
                        "createUser",
                        exporter_username,
                        pwd=exporter_password,
                        roles=[
                            {"role": "clusterMonitor", "db": "admin"},
                            {"role": "read", "db": "admin"},
                        ],
                    )
                    print("Created the least-privilege Prometheus exporter user.")
                except OperationFailure as error:
                    if error.code != 51003:
                        raise
                    print("Prometheus exporter user already exists.")
                finally:
                    replica_client.close()
                return 0
            time.sleep(3)

        raise TimeoutError("Replica set did not reach one PRIMARY and two SECONDARY members.")
    except PyMongoError as error:
        print(f"Replica-set initialization failed: {error}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
