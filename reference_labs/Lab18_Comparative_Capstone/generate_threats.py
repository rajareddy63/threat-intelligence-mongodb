"""Deterministic synthetic threat-intelligence event generator."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterator

SOURCES = ("MISP", "AlienVault OTX", "Abuse.ch", "OpenPhish", "Internal SOC")
TARGETS = ("Northstar Bank", "Acme Health", "Contoso Cloud", "Globex Energy", "Fabrikam Retail", "Initech Systems", "Umbrella Logistics", "Wayne Research")
SEVERITIES = ("low", "medium", "high", "critical")


def generate_threats(count: int, seed: int = 18) -> Iterator[dict]:
    """Yield repeatable records with a broad event range and shared indicators."""
    if count < 0:
        raise ValueError("count must be non-negative")
    rng = random.Random(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    indicator_pool = [f"198.{rng.randint(18, 220)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}" for _ in range(5000)]
    domains = [f"{uuid.uuid5(uuid.NAMESPACE_DNS, str(i)).hex[:12]}.threat-example.net" for i in range(2000)]
    for index in range(count):
        kind = rng.choice(("ipv4", "domain", "url", "sha256"))
        indicator = rng.choice(indicator_pool) if kind == "ipv4" else (
            rng.choice(domains) if kind == "domain" else
            f"https://{rng.choice(domains)}/payload/{rng.randrange(100)}" if kind == "url" else
            uuid.uuid5(uuid.NAMESPACE_OID, str(rng.randrange(10000))).hex * 2
        )
        observed = now - timedelta(seconds=rng.randrange(365 * 24 * 3600))
        yield {
            "threat_id": str(uuid.UUID(int=rng.getrandbits(128), version=4)),
            "source": rng.choice(SOURCES),
            "indicator": indicator,
            "indicator_type": kind,
            "severity": rng.choice(SEVERITIES),
            "confidence": round(rng.uniform(0.35, 0.99), 3),
            "target": rng.choice(TARGETS),
            "observed_at": observed,
            "first_seen": observed - timedelta(seconds=rng.randrange(0, 86400)),
            "spread_count": rng.randint(1, 500),
            "status": rng.choice(("active", "monitoring", "resolved")),
            "tags": rng.sample(("phishing", "botnet", "ransomware", "c2", "credential-theft", "malware"), k=2),
        }
