import json
import time
from fraud_query_service import FraudQueryService

service = FraudQueryService()

sample_txn = {
    "txn_id": "TXN-1001",
    "user_id": "U-1001",
    "amount": 1450.75,
    "merchant": "Test Merchant",
    "timestamp": "2026-11-15T10:00:00Z",
    "risk_score": 0.84,
}

print("FraudQueryService demonstration")
print(json.dumps(service.analyze_fraud("TXN-1001", "U-1001"), indent=2, default=str))
