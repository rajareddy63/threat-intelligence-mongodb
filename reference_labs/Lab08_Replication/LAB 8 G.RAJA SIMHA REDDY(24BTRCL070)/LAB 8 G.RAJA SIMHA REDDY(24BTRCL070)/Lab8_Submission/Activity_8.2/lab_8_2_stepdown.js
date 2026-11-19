// Lab 8.2 - mongosh file: force a failover and watch the election.
// Run against the CURRENT PRIMARY by lab_8_2_failover_observer.py:
//     mongosh --port <primary-port> --file lab_8_2_stepdown.js

function members()  { return rs.status().members; }
function primaryName() {
  try {
    const p = members().find(m => m.stateStr === "PRIMARY");
    return p ? p.name : null;
  } catch (e) { return null; }
}
function show(title) {
  print("\n=== " + title + " ===");
  try {
    members().forEach(m =>
      print(m.name.padEnd(30) + m.stateStr.padEnd(12) + "health=" + m.health));
  } catch (e) { print("(status unavailable: " + e.message + ")"); }
}

const before = primaryName();
show("rs.status() BEFORE stepDown");
print("\nCurrent PRIMARY: " + before);

print("\n>>> rs.stepDown(30)   (old primary may not stand for election for 30 s)");
const t0 = Date.now();
try {
  rs.stepDown(30);
} catch (e) {
  // Stepping down closes client connections, so a network error is NORMAL here.
  print("stepDown issued - connection was closed by the server (expected): " +
        e.message.substring(0, 70));
}

// Watch the election: poll every 500 ms until a different primary appears
let after = null;
for (let i = 0; i < 80; i++) {
  after = primaryName();
  if (after && after !== before) break;
  after = null;
  sleep(500);
}
const secs = ((Date.now() - t0) / 1000).toFixed(1);
if (after) {
  print("\nElection finished in ~" + secs + " s");
  print("*** PRIMARY CHANGED: " + before + "  ->  " + after + " ***");
} else {
  print("\nNo new primary after 40 s - check rs.status()");
}

show("rs.status() AFTER election");
