from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from bson import ObjectId

from lab_01_multitenant_api import TaskAPI
from lab_02_tenant_migration import migrate_tenant, rollback_tenant


class MemoryCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    def find(self, query: dict) -> list[dict]:
        return [
            document.copy()
            for document in self.documents
            if all(document.get(key) == value for key, value in query.items())
        ]

    def count_documents(self, query: dict) -> int:
        return len(self.find(query))

    def update_one(self, query: dict, update: dict, *, upsert: bool) -> None:
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                document.update(update["$set"])
                return
        if upsert:
            self.documents.append({**query, **update["$set"]})

    def create_index(self, _keys: list) -> None:
        pass


class MemoryDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, MemoryCollection] = {}

    def __getitem__(self, name: str) -> MemoryCollection:
        return self.collections.setdefault(name, MemoryCollection())


class MemoryClient:
    def __init__(self) -> None:
        self.databases: dict[str, MemoryDatabase] = {}

    def __getitem__(self, name: str) -> MemoryDatabase:
        return self.databases.setdefault(name, MemoryDatabase())


class TaskApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MagicMock()
        self.api = TaskAPI(self.database, rate_limit=2, rate_window_seconds=60)

    def test_update_scopes_filter_by_tenant_and_id(self) -> None:
        task_id = ObjectId()
        self.database.__getitem__.return_value.update_one.return_value.matched_count = 1

        self.assertTrue(self.api.update_task("tenant-a", task_id, title="Updated"))
        args = self.database.__getitem__.return_value.update_one.call_args.args
        self.assertEqual(args[0], {"_id": task_id, "tenant_id": "tenant-a"})

    def test_rate_limit_is_per_tenant_and_window(self) -> None:
        collection = self.database.__getitem__.return_value
        collection.find_one_and_update.side_effect = [
            {"count": 1},
            {"count": 2},
            {"count": 3},
            {"count": 1},
        ]

        self.assertTrue(self.api.check_rate_limit("tenant-a", now=125))
        self.assertTrue(self.api.check_rate_limit("tenant-a", now=125))
        self.assertFalse(self.api.check_rate_limit("tenant-a", now=125))
        self.assertTrue(self.api.check_rate_limit("tenant-b", now=125))
        first_filter = collection.find_one_and_update.call_args_list[0].args[0]
        self.assertEqual(first_filter["_id"], "tenant-a:120")
        last_filter = collection.find_one_and_update.call_args_list[-1].args[0]
        self.assertEqual(last_filter["_id"], "tenant-b:120")

    def test_invalid_tenant_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.api.list_tasks("tenant/other")


class MigrationTests(unittest.TestCase):
    def test_migration_upserts_by_stable_task_key_and_is_repeatable(self) -> None:
        client = MemoryClient()
        source = client["saas_app"]["tasks"]
        document = {"_id": ObjectId(), "task_key": "stable-1", "tenant_id": "tenant-a"}
        source.documents.append(document)

        first = migrate_tenant(client, "tenant-a")
        second = migrate_tenant(client, "tenant-a")
        target = client["tenant_tenant-a"]["tasks"]

        self.assertEqual(first.target_count, 1)
        self.assertEqual(second.target_count, 1)
        self.assertEqual(len(target.documents), 1)

    def test_dry_run_does_not_write(self) -> None:
        client = MagicMock()
        source = client.__getitem__.return_value.__getitem__.return_value
        target = client.__getitem__.return_value.__getitem__.return_value
        source.find.return_value = [{"task_key": "stable-1", "tenant_id": "tenant-a"}]

        result = migrate_tenant(client, "tenant-a", dry_run=True)

        self.assertTrue(result.dry_run)
        target.update_one.assert_not_called()
        target.create_index.assert_not_called()

    def test_rollback_drops_only_dedicated_database(self) -> None:
        client = MagicMock()

        rollback_tenant(client, "tenant-a")

        client.drop_database.assert_called_once_with("tenant_tenant-a")

    def test_missing_stable_key_fails_before_writing(self) -> None:
        client = MagicMock()
        collection = client.__getitem__.return_value.__getitem__.return_value
        collection.find.return_value = [{"_id": ObjectId(), "tenant_id": "tenant-a"}]

        with self.assertRaisesRegex(ValueError, "stable task_key"):
            migrate_tenant(client, "tenant-a")
        collection.update_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
