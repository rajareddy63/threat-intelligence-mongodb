CREATE CONSTRAINT threat_id IF NOT EXISTS FOR (t:Threat) REQUIRE t.threat_id IS UNIQUE;
CREATE INDEX threat_indicator IF NOT EXISTS FOR (t:Threat) ON (t.indicator);
CREATE INDEX threat_target IF NOT EXISTS FOR (t:Threat) ON (t.target);
CREATE INDEX threat_observed IF NOT EXISTS FOR (t:Threat) ON (t.observed_at);
