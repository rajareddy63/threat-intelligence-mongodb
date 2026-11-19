db = db.getSiblingDB('threatintel');
db.createCollection('threats');
db.threats.createIndex({ threat_id: 1 }, { unique: true, name: 'threat_id_unique' });
db.threats.createIndex({ indicator: 1, observed_at: -1 }, { name: 'indicator_history' });
db.threats.createIndex({ target: 1, observed_at: -1 }, { name: 'target_spread' });
db.threats.createIndex({ observed_at: 1, source: 1 }, { name: 'daily_volume' });
