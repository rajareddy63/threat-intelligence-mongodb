import unittest
from datetime import datetime, timezone

from benchmark import run_benchmarks
from generate_threats import generate_threats
from mongo_operations import MongoStore
from run_all import verified_benchmark_stores


class MutatingCollection:
    def bulk_write(self, operations, ordered=False):
        self.operations = operations


class FakeMongoStore:
    def threat_history(self, indicator):
        self.indicator = indicator

    def target_spread(self, target):
        self.target = target

    def daily_volume(self, start, end):
        assert start.tzinfo is not None and end.tzinfo is not None

    def bulk_insert(self, rows, batch_size):
        assert len(rows) == batch_size


class FakeCassandraStore:
    def threat_history(self, indicator):
        pass

    def target_spread(self, target):
        pass

    def daily_volume(self, start, end):
        assert start.year > 2000 and end > start

    def bulk_insert(self, rows, batch_size):
        pass


class FakeNeo4jStore:
    def threat_history(self, indicator):
        pass

    def target_spread(self, target):
        pass

    def daily_volume(self, start, end):
        assert start.tzinfo is not None and end > start

    def bulk_insert(self, rows, batch_size):
        pass


class ProjectTests(unittest.TestCase):
    def test_generator_is_repeatable_and_sized(self):
        first = list(generate_threats(20, seed=18))
        second = list(generate_threats(20, seed=18))
        self.assertEqual(len(first), 20)
        self.assertEqual(first, second)
        self.assertEqual(len({record["threat_id"] for record in first}), 20)

    def test_benchmark_routes_daily_arguments_and_reports_medians(self):
        probe = next(generate_threats(1))
        stores = {"mongo": FakeMongoStore(), "cassandra": FakeCassandraStore(), "neo4j": FakeNeo4jStore()}
        output = run_benchmarks(stores, probe, runs=2, insert_batch_size=3)
        for name in stores:
            self.assertEqual(output["databases"][name]["queries"]["daily_volume"]["successful_runs"], 2)
            self.assertEqual(output["databases"][name]["successful_insert_runs"], 2)
            self.assertGreater(output["databases"][name]["median_insert_throughput_records_per_second"], 0)

    def test_negative_record_count_rejected(self):
        with self.assertRaises(ValueError):
            list(generate_threats(-1))

    def test_mongo_bulk_insert_does_not_mutate_shared_records(self):
        store = MongoStore.__new__(MongoStore)
        store.collection = MutatingCollection()
        records = [{"threat_id": "shared-record"}]
        self.assertEqual(store.bulk_insert(records), 1)
        self.assertEqual(len(store.collection.operations), 1)
        self.assertNotIn("_id", records[0])

    def test_incomplete_databases_are_excluded_from_benchmarks(self):
        stores = {"complete": object(), "partial": object(), "failed": object()}
        status = {
            "complete": {"loaded_records": 100, "load_error": None},
            "partial": {"loaded_records": 99, "load_error": "count mismatch"},
            "failed": {"loaded_records": 0, "load_error": "write timeout"},
        }
        self.assertEqual(verified_benchmark_stores(stores, status, 100), {"complete": stores["complete"]})


if __name__ == "__main__":
    unittest.main()
