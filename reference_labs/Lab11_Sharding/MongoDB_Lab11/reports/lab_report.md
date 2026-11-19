# MongoDB Lab 11 – Sharding and Hotspot Detection

## Environment
- MongoDB: 7.0
- Deployment: Docker Compose, one config-server replica set, two single-member shard replica sets, and one mongos router.
- Dataset: 10,000 documents per collection.
- Database: `lab11`

## Lab 11.1 – Shard key decision matrix

| Candidate | Cardinality | Distribution | Query targeting | Assessment |
|---|---|---|---|---|
| `order_id` | High | Usually even if values are well distributed | Excellent for exact order ID; poor for customer lookups | Useful when most queries use order ID |
| `customer_id` | High in a large store, but may have skew | Can be uneven because customers place different numbers of orders | Good for customer equality queries | Good targeting, possible hot customers |
| `order_date` | High over time | New inserts concentrate at the high end of the key range | Good for date-range queries | Risk of an insert hotspot |
| Hashed `customer_id` | High | Hashing generally spreads values more evenly | Good for equality queries on customer ID; range queries on original customer ID are inefficient | Recommended for a customer-centric workload |

### Recommendation
For an order system where customer-specific order lookups are common and write distribution matters, use `{ customer_id: "hashed" }`. It spreads customer key values across the hashed key space while allowing equality queries on a customer ID to be routed efficiently. It does not make every workload optimal: queries by date or order ID may need to contact multiple shards. The final choice should be validated against actual query frequency and customer-order skew.

## MongoDB 5.0+ resharding activity

A simplified operational sequence:
1. Check the current shard key, indexes, shard health, and available disk space.
2. Select a shard key that matches the dominant query patterns and distribution needs.
3. Run `sh.reshardCollection()` or the equivalent `reshardCollection` admin command on the target namespace.
4. Monitor the resharding operation using `$currentOp` and server logs.
5. Allow MongoDB to copy data and catch up with concurrent writes.
6. Verify completion, the new key, chunk placement, and application query plans.

Example (run only in a test environment and after reviewing the collection's indexes):
```javascript
sh.reshardCollection("lab11.orders", { customer_id: "hashed" })
```

Important limitations and operational considerations:
- Resharding is resource-intensive and needs spare disk, CPU, and I/O capacity.
- It can take significant time on large collections.
- A final critical section can briefly affect writes.
- Unique-index requirements and shard-key compatibility must be checked before starting.
- Resharding is not supported for every collection type or special feature; consult the documentation for the exact MongoDB release.
- Monitor the operation and plan a maintenance window for production workloads.

## Lab 11.2 – Hotspot detection

### Method
1. Create `hotspot_data` with ascending range key `{ ts: 1 }`.
2. Create `even_data` with hashed key `{ user_id: "hashed" }`.
3. Insert 10,000 documents into each collection.
4. Inspect `collStats` and per-shard statistics through `mongos`.
5. Run a timestamp range query and a range query on the original `user_id` field; compare `explain()` output.

### Expected interpretation
- With an ascending timestamp shard key, new values belong to the upper end of the key space. Inserts can concentrate on the shard owning that upper range, creating a write hotspot until chunks are split/moved or the data distribution changes.
- A hashed key spreads distinct key values across the hashed key space. Equality queries on the original hashed field can target the relevant shard, but range queries on the original value generally cannot use the hashed ordering efficiently and may scatter to multiple shards.
- Exact shard counts depend on MongoDB version, chunk creation, balancer activity, insertion timing, and cluster state. Do not assume a fixed 9,500/500 or 5,000/5,000 split; report the measured output.

### When a ranged shard key is still appropriate
A ranged key is useful when the workload frequently performs range queries, locality-based queries, or prefix queries and the key distribution/write pattern is not monotonically increasing at a single hot edge. Compound keys, such as a tenant or category prefix plus a time component, may help, but must be tested for cardinality, skew, and write concentration.

## Results to fill after running
- `hotspot_data` per-shard document counts: ____________________
- `even_data` per-shard document counts: ____________________
- Timestamp explain targeted shards: ____________________
- Hashed-field range explain targeted shards: ____________________
- Screenshot filenames: ____________________

## Conclusion
The shard key should balance query targeting and data distribution. Hashed keys are effective for high-volume equality lookups and write distribution, while ranged keys are better for range-based access patterns. Monotonically increasing ranged keys can create a hot shard at the active end of the key space.
