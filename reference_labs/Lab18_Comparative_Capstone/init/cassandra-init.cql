CREATE KEYSPACE IF NOT EXISTS threatintel WITH replication = {'class':'SimpleStrategy','replication_factor':1};
USE threatintel;
CREATE TABLE IF NOT EXISTS history_by_indicator (indicator text, observed_at timestamp, threat_id text, source text, severity text, target text, spread_count int, PRIMARY KEY (indicator, observed_at, threat_id)) WITH CLUSTERING ORDER BY (observed_at DESC);
CREATE TABLE IF NOT EXISTS target_spread_by_target (target text, observed_at timestamp, threat_id text, source text, severity text, spread_count int, PRIMARY KEY (target, observed_at, threat_id)) WITH CLUSTERING ORDER BY (observed_at DESC);
CREATE TABLE IF NOT EXISTS daily_volume_by_day (day date, source text, observed_at timestamp, threat_id text, PRIMARY KEY (day, source, observed_at, threat_id));
