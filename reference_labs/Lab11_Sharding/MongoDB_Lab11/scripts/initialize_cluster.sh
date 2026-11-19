#!/bin/bash
set -e

echo "Waiting for MongoDB processes..."
until mongosh "mongodb://mongos:27017" --quiet --eval 'db.adminCommand({ping:1}).ok' >/dev/null 2>&1; do
  sleep 2
done

echo "Initiating config server replica set..."
mongosh "mongodb://configsvr:27019" --quiet --eval '
try {
  rs.status();
} catch (e) {
  rs.initiate({_id:"configReplSet", configsvr:true, members:[{_id:0, host:"configsvr:27019"}]});
}
'
sleep 8

echo "Initiating shard replica sets..."
mongosh "mongodb://shard1:27018" --quiet --eval '
try { rs.status(); } catch (e) {
  rs.initiate({_id:"shard1ReplSet", members:[{_id:0, host:"shard1:27018"}]});
}
'
mongosh "mongodb://shard2:27018" --quiet --eval '
try { rs.status(); } catch (e) {
  rs.initiate({_id:"shard2ReplSet", members:[{_id:0, host:"shard2:27018"}]});
}
'
sleep 10

echo "Registering shards with mongos..."
mongosh "mongodb://mongos:27017" --quiet --eval '
sh.addShard("shard1ReplSet/shard1:27018");
sh.addShard("shard2ReplSet/shard2:27018");
sh.enableSharding("lab11");
'

echo "Cluster initialization complete."
