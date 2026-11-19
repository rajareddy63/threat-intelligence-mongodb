import argparse
import os
import sys
import time

from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure, PyMongoError


def connect() -> MongoClient:
    uri = os.environ.get(
        "MONGODB_URI",
        "mongodb://labadmin:REPLACE_WITH_GENERATED_HEX_SECRET@localhost:37017,localhost:37018,localhost:37019/"
        "?replicaSet=rs0&authSource=admin&retryWrites=true",
    )
    return MongoClient(uri, serverSelectionTimeoutMS=5000, retryWrites=True)


def show_status(client: MongoClient) -> None:
    status = client.admin.command("replSetGetStatus")
    for member in status["members"]:
        print(f'{member["name"]}: {member["stateStr"]}')


def write_and_read(client: MongoClient) -> None:
    collection = client["lab13"]["demo"]
    document = {"_id": "exercise-13-demo", "message": "PyMongo replica-set read/write verified"}
    collection.replace_one({"_id": document["_id"]}, document, upsert=True)
    print(f"Inserted/read: {collection.find_one({'_id': document['_id']})}")


def wait_for_new_primary(client: MongoClient, old_primary: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            hello = client.admin.command("hello")
            primary = hello.get("primary")
            if primary and primary != old_primary:
                print(f"FAILOVER VERIFIED: old primary {old_primary}; new primary {primary}")
                return
        except (AutoReconnect, ConnectionFailure):
            pass
        time.sleep(2)
    raise TimeoutError(f"No primary other than {old_primary} was elected within {timeout} seconds.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise 13 replica-set status, writes, reads, and failover.")
    parser.add_argument("action", choices=("status", "write-read", "failover"), nargs="?", default="status")
    parser.add_argument("--timeout", type=int, default=120, help="Failover election timeout in seconds.")
    args = parser.parse_args()
    client = connect()
    try:
        if args.action == "status":
            show_status(client)
        elif args.action == "write-read":
            write_and_read(client)
        else:
            old_primary = client.admin.command("hello").get("primary")
            if not old_primary:
                raise RuntimeError("The replica set has no current primary.")
            print(f"Stepping down current primary {old_primary}; the driver will observe election.")
            try:
                client.admin.command({"replSetStepDown": 60, "force": True})
            except (AutoReconnect, ConnectionFailure):
                pass
            wait_for_new_primary(client, old_primary, args.timeout)
            write_and_read(client)
        return 0
    except (PyMongoError, TimeoutError, RuntimeError) as error:
        print(f"Operation failed: {error}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
