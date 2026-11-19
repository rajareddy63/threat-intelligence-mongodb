import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "fraud")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "transactions")

CASSANDRA_CONTACT_POINTS = [p.strip() for p in os.getenv("CASSANDRA_CONTACT_POINTS", "127.0.0.1").split(",") if p.strip()]
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "user_activity")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "LocalPass123")
