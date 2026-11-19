"""Run an end-to-end multi-tenant API and migration demonstration."""

from __future__ import annotations

import argparse
import os
from pprint import pprint

from pymongo import MongoClient

from lab_01_multitenant_api import TaskAPI
from lab_02_tenant_migration import migrate_tenant


def run_demo(uri: str) -> None:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        api = TaskAPI(client["saas_app"], rate_limit=3, rate_window_seconds=60)
        tenant_a = "demo-acme"
        tenant_b = "demo-globex"
        task_a = api.create_task(tenant_a, "Prepare quarterly report", "Q4 planning")
        api.create_task(tenant_b, "Review deployment", "Production checklist")

        print("Tenant A sees only its own tasks:")
        pprint(api.list_tasks(tenant_a))
        print("Cross-tenant update rejected:", not api.update_task(
            tenant_b, task_a["_id"], title="Unauthorized edit"
        ))

        print("Rate-limit results (limit=3):")
        pprint([api.check_rate_limit(tenant_a) for _ in range(4)])

        print("Migration dry run:")
        pprint(migrate_tenant(client, tenant_a, dry_run=True).to_dict())
        print("First migration:")
        first = migrate_tenant(client, tenant_a)
        pprint(first.to_dict())
        print("Repeat migration (target count should remain stable):")
        second = migrate_tenant(client, tenant_a)
        pprint(second.to_dict())
        if first.target_count != second.target_count:
            raise RuntimeError("idempotency check failed: target document count changed")
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uri",
        default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        help="MongoDB connection URI (or set MONGODB_URI)",
    )
    args = parser.parse_args()
    run_demo(args.uri)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
