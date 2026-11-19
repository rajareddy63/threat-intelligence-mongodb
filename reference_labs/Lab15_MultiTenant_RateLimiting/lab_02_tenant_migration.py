"""Idempotently copy one tenant from a shared collection to a dedicated database."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import asdict, dataclass
from typing import Any

from pymongo import ASCENDING, MongoClient

TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")


def validate_tenant_id(tenant_id: str) -> str:
    if not TENANT_PATTERN.fullmatch(tenant_id):
        raise ValueError("tenant_id must be 1-63 letters, digits, underscores, or hyphens")
    return tenant_id


@dataclass(frozen=True)
class MigrationResult:
    tenant_id: str
    source_count: int
    target_count: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def migrate_tenant(
    client: Any,
    tenant_id: str,
    *,
    source_database: str = "saas_app",
    dry_run: bool = False,
) -> MigrationResult:
    tenant_id = validate_tenant_id(tenant_id)
    source = client[source_database]["tasks"]
    target = client[f"tenant_{tenant_id}"]["tasks"]
    documents = list(source.find({"tenant_id": tenant_id}))
    source_count = len(documents)

    if dry_run:
        target_count = target.count_documents({})
        return MigrationResult(tenant_id, source_count, target_count, True)

    for document in documents:
        task_key = document.get("task_key")
        if not isinstance(task_key, str) or not task_key:
            raise ValueError(
                f"source document {document.get('_id')} has no stable task_key; "
                "migration stopped without deleting source data"
            )
        target.update_one(
            {"task_key": task_key},
            {"$set": {key: value for key, value in document.items() if key != "_id"}},
            upsert=True,
        )
    target.create_index([("tenant_id", ASCENDING), ("created_at", ASCENDING)])
    target_count = target.count_documents({"tenant_id": tenant_id})
    return MigrationResult(tenant_id, source_count, target_count, False)


def rollback_tenant(client: Any, tenant_id: str) -> None:
    """Drop only the tenant's dedicated database; shared source data is untouched."""
    tenant_id = validate_tenant_id(tenant_id)
    client.drop_database(f"tenant_{tenant_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True, help="Tenant ID to migrate or roll back")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    parser.add_argument("--rollback", action="store_true", help="Drop the dedicated tenant database")
    parser.add_argument(
        "--uri",
        default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        help="MongoDB connection URI (or set MONGODB_URI)",
    )
    parser.add_argument("--source-database", default="saas_app")
    args = parser.parse_args()

    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        if args.rollback:
            rollback_tenant(client, args.tenant)
            print(f"Rolled back tenant_{args.tenant}; shared source documents were preserved.")
            return 0
        result = migrate_tenant(
            client,
            args.tenant,
            source_database=args.source_database,
            dry_run=args.dry_run,
        )
        print(result.to_dict())
        if not args.dry_run and result.source_count != result.target_count:
            raise RuntimeError(
                f"migration count mismatch: source={result.source_count}, "
                f"target={result.target_count}"
            )
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
