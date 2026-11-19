import unittest
from unittest.mock import Mock, patch

from fraud_query_service import FraudQueryService, CircuitBreaker


class CircuitBreakerTests(unittest.TestCase):
    def test_breaker_opens_after_three_failures(self):
        breaker = CircuitBreaker("mongo")
        breaker.record_failure()
        breaker.record_failure()
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()
        self.assertFalse(breaker.allow_request())

    def test_breaker_resets_on_success(self):
        breaker = CircuitBreaker("mongo")
        breaker.record_failure(); breaker.record_failure(); breaker.record_failure()
        self.assertFalse(breaker.allow_request())
        breaker.record_success()
        self.assertTrue(breaker.allow_request())


class FraudQueryServiceTests(unittest.TestCase):
    @patch.object(FraudQueryService, "_connect_mongo", return_value=Mock())
    @patch.object(FraudQueryService, "_connect_cassandra", return_value=Mock())
    @patch.object(FraudQueryService, "_connect_neo4j", return_value=Mock())
    def test_get_transaction(self, *_):
        service = FraudQueryService()
        service.mongo_client = {"fraud": {"transactions": Mock()}}
        collection = Mock()
        collection.find_one.return_value = {"txn_id": "T1", "risk_score": 0.7}
        service.mongo_client = {"fraud": {"transactions": collection}}
        result = service.get_transaction("T1")
        self.assertEqual(result["txn_id"], "T1")

    @patch.object(FraudQueryService, "_connect_mongo", return_value=Mock())
    @patch.object(FraudQueryService, "_connect_cassandra", return_value=Mock())
    @patch.object(FraudQueryService, "_connect_neo4j", return_value=Mock())
    def test_get_user_profile(self, *_):
        service = FraudQueryService()
        service.cassandra_session = Mock()
        row = Mock(user_id="U1", event_time=123, event_type="login", amount=10.0, merchant="Shop", details="test")
        service.cassandra_session.execute.return_value = [row]
        result = service.get_user_profile("U1")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["events"][0]["user_id"], "U1")

    @patch.object(FraudQueryService, "_connect_mongo", return_value=Mock())
    @patch.object(FraudQueryService, "_connect_cassandra", return_value=Mock())
    @patch.object(FraudQueryService, "_connect_neo4j", return_value=Mock())
    def test_detect_fraud_rings(self, *_):
        service = FraudQueryService()
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        session.run.return_value = [
            {"user_id": "U2", "hops": 2, "path": ["U1", "U2"]},
            {"user_id": "U3", "hops": 3, "path": ["U1", "U4", "U3"]},
        ]
        service.neo4j_driver = Mock()
        service.neo4j_driver.session.return_value = session
        result = service.detect_fraud_rings("U1", max_hops=3)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["related_accounts"]), 2)

    def test_connection_failure_returns_partial_result(self):
        service = FraudQueryService(mongo_uri="mongodb://badhost:27017")
        service.mongo_client = None
        result = service.get_transaction("T1")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["database"], "mongo")

    def test_merge_response_works(self):
        service = FraudQueryService()
        service.get_transaction = Mock(return_value={"txn_id": "T1", "risk_score": 0.82, "user_id": "U1"})
        service.get_user_profile = Mock(return_value={"status": "ok", "events": [{"event_type": "login"}]})
        service.detect_fraud_rings = Mock(return_value={"status": "ok", "related_accounts": [{"user_id": "U2", "hops": 2}]})
        result = service.analyze_fraud("T1", "U1")
        self.assertEqual(result["summary"]["transaction_id"], "T1")
        self.assertEqual(result["summary"]["related_account_count"], 1)


if __name__ == "__main__":
    unittest.main()
