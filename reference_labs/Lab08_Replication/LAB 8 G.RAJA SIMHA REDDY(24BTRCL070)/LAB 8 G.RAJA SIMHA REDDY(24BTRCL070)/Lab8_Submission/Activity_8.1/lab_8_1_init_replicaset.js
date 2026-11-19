// Lab 8.1 - mongosh file: initiate a 3-member replica set and show its status.
// Run inside mongo-rs0-1 (port 27017) by lab_8_1_deploy_replicaset.py:
//     mongosh --port 27017 --file lab_8_1_init_replicaset.js

print("=== rs.initiate() ===");
try {
  printjson(rs.initiate({
    _id: "rs0",
    members: [
      { _id: 0, host: "mongo-rs0-1:27017" },
      { _id: 1, host: "mongo-rs0-2:27017" },
      { _id: 2, host: "mongo-rs0-3:27017" }
    ]
  }));
} catch (e) {
  print("rs.initiate skipped: " + e.message);   // e.g. already initiated
}

// Wait (max 60 s) until the election finishes and a PRIMARY exists
print("\nWaiting for an election to finish...");
let primary = null;
for (let i = 0; i < 60 && !primary; i++) {
  try {
    primary = rs.status().members.find(m => m.stateStr === "PRIMARY");
  } catch (e) { /* not ready yet */ }
  if (!primary) sleep(1000);
}
print(primary ? "PRIMARY elected: " + primary.name : "No primary yet!");

// rs.status() summary: who is primary / secondary and are they healthy?
print("\n=== rs.status() summary ===");
rs.status().members.forEach(m => {
  print(m.name.padEnd(30) + m.stateStr.padEnd(12) + "health=" + m.health);
});

// Replica-set configuration: votes and priorities
print("\n=== rs.conf() summary ===");
rs.conf().members.forEach(m => {
  print(m.host.padEnd(30) + "priority=" + m.priority + "  votes=" + m.votes +
        "  arbiterOnly=" + m.arbiterOnly);
});
