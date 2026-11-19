// Run this script through mongosh connected to mongos:
// mongosh "mongodb://localhost:27017" scripts/setup_collections.js

sh.enableSharding("lab11");
const d = db.getSiblingDB("lab11");

// Clean previous lab run so the experiment is repeatable.
d.hotspot_data.drop();
d.even_data.drop();

// Timestamp range shard key: a monotonically increasing key.
d.createCollection("hotspot_data");
sh.shardCollection("lab11.hotspot_data", { ts: 1 });

// Hashed key: pre-split hashed key space into two initial chunks
// so both shards can receive data in this two-shard demonstration.
d.createCollection("even_data");
sh.shardCollection("lab11.even_data", { user_id: "hashed" }, false, { numInitialChunks: 2 });

print("Collections created and sharded.");
sh.status();
