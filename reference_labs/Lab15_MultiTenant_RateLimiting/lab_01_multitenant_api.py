"""MongoDB-backed task API with shared-collection tenant isolation."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, MongoClient, ReturnDocument

TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")


def validate_tenant_id(tenant_id: str) -> str:
    if not isinstance(tenant_id, str) or not TENANT_PATTERN.fullmatch(tenant_id):
        raise ValueError("tenant_id must be 1-63 letters, digits, underscores, or hyphens")
    return tenant_id


class TaskAPI:
    """Keep tenant scoping in the data-access layer for every task operation."""

    def __init__(
        self,
        database: Any,
        *,
        rate_limit: int = 100,
        rate_window_seconds: int = 60,
    ) -> None:
        if rate_limit < 1 or rate_window_seconds < 1:
            raise ValueError("rate_limit and rate_window_seconds must be positive")
        self.tasks = database["tasks"]
        self.rate_limits = database["rate_limits"]
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self.tasks.create_index([("tenant_id", ASCENDING), ("created_at", ASCENDING)])

    def check_rate_limit(self, tenant_id: str, *, now: float | None = None) -> bool:
        tenant_id = validate_tenant_id(tenant_id)
        current = time.time() if now is None else now
        window_start = int(current // self.rate_window_seconds) * self.rate_window_seconds
        window_id = f"{tenant_id}:{window_start}"
        result = self.rate_limits.find_one_and_update(
            {"_id": window_id},
            {
                "$inc": {"count": 1},
                "$setOnInsert": {
                    "tenant_id": tenant_id,
                    "window_start": window_start,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(result["count"]) <= self.rate_limit

    def create_task(
        self, tenant_id: str, title: str, description: str = ""
    ) -> dict[str, Any]:
        tenant_id = validate_tenant_id(tenant_id)
        if not title or not title.strip():
            raise ValueError("title must not be empty")
        task = {
            "task_key": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "title": title.strip(),
            "description": description.strip(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        inserted = self.tasks.insert_one(task)
        task["_id"] = inserted.inserted_id
        return task

    def list_tasks(self, tenant_id: str) -> list[dict[str, Any]]:
        tenant_id = validate_tenant_id(tenant_id)
        return list(self.tasks.find({"tenant_id": tenant_id}).sort("created_at", ASCENDING))

    def update_task(
        self,
        tenant_id: str,
        task_id: str | ObjectId,
        *,
        title: str | None = None,
        description: str | None = None,
    ) -> bool:
        tenant_id = validate_tenant_id(tenant_id)
        if isinstance(task_id, ObjectId):
            object_id = task_id
        elif isinstance(task_id, str) and ObjectId.is_valid(task_id):
            object_id = ObjectId(task_id)
        else:
            raise ValueError("task_id must be a valid MongoDB ObjectId")

        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if title is not None:
            if not title.strip():
                raise ValueError("title must not be empty")
            updates["title"] = title.strip()
        if description is not None:
            updates["description"] = description.strip()
        result = self.tasks.update_one(
            {"_id": object_id, "tenant_id": tenant_id},
            {"$set": updates},
        )
        return result.matched_count == 1


def connect_api(uri: str, database_name: str = "saas_app") -> tuple[MongoClient, TaskAPI]:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return client, TaskAPI(client[database_name])
