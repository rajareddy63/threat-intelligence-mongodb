import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import app


class FakeAdmin:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.responses = {
            "serverStatus": {
                "connections": {"current": 12, "available": 400},
                "opcounters": {"insert": 4, "query": 6},
                "wiredTiger": {
                    "cache": {
                        "bytes currently in the cache": 80,
                        "maximum bytes configured": 100,
                    }
                },
            },
            "replSetGetStatus": {
                "set": "rs0",
                "myState": 1,
                "members": [
                    {"name": "mongo1:27017", "stateStr": "PRIMARY", "health": 1, "optimeDate": now},
                    {
                        "name": "mongo2:27017",
                        "stateStr": "SECONDARY",
                        "health": 1,
                        "optimeDate": now - timedelta(seconds=12),
                    },
                ],
            },
        }

    def command(self, name: str) -> dict:
        return self.responses[name]


class FakeClient:
    admin = FakeAdmin()


class MonitoringTests(unittest.TestCase):
    def test_collects_required_dashboard_metrics(self) -> None:
        metrics = app.collect_metrics(FakeClient())
        self.assertEqual(metrics["connections"]["current"], 12)
        self.assertEqual(metrics["opcounters"]["insert"], 4)
        self.assertEqual(metrics["wiredTigerCache"]["usedPercent"], 80.0)
        self.assertEqual(metrics["replicaSet"]["primary"], "mongo1:27017")
        self.assertEqual(metrics["replicaSet"]["maximumLagSeconds"], 12.0)

    def test_cache_and_lag_thresholds_trigger_webhook_alerts(self) -> None:
        metrics = app.collect_metrics(FakeClient())
        with (
            patch.object(app, "CACHE_WARNING_PERCENT", 80),
            patch.object(app, "REPLICATION_LAG_WARNING_SECONDS", 10),
            patch.object(app, "WEBHOOK_URL", "http://example.test/alerts"),
            patch.object(app, "_send_webhook") as send_webhook,
            patch.dict(app._alert_last_sent, {}, clear=True),
        ):
            alerts = app.evaluate_alerts(metrics)

        self.assertEqual({alert["type"] for alert in alerts}, {"wiredtiger_cache", "replication_lag"})
        self.assertEqual(send_webhook.call_count, 2)

    def test_below_threshold_does_not_send_alerts(self) -> None:
        metrics = app.collect_metrics(FakeClient())
        metrics["wiredTigerCache"]["usedPercent"] = 79.9
        metrics["replicaSet"]["maximumLagSeconds"] = 10
        with (
            patch.object(app, "WEBHOOK_URL", "http://example.test/alerts"),
            patch.object(app, "_send_webhook") as send_webhook,
        ):
            alerts = app.evaluate_alerts(metrics)
        self.assertEqual(alerts, [])
        send_webhook.assert_not_called()


if __name__ == "__main__":
    unittest.main()
