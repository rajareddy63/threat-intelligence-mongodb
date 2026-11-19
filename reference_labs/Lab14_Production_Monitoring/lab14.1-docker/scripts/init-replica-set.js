const config = {
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27017", priority: 1 },
    { _id: 2, host: "mongo3:27017", priority: 1 }
  ]
};

try {
  const status = rs.status();
  if (status.ok !== 1) {
    throw new Error("Replica set is not initialized");
  }
  print("Replica set already initialized");
} catch (error) {
  print("Initializing replica set");
  rs.initiate(config);
}

const deadline = Date.now() + 120000;
while (Date.now() < deadline) {
  try {
    const status = rs.status();
    if (status.members.some((member) => member.stateStr === "PRIMARY")) {
      printjson({
        set: status.set,
        members: status.members.map((member) => ({
          name: member.name,
          state: member.stateStr
        }))
      });
      quit(0);
    }
  } catch (error) {
    // The node can briefly reject status requests while starting the replica set.
  }
  sleep(2000);
}

throw new Error("Replica set did not elect a primary within 120 seconds");
