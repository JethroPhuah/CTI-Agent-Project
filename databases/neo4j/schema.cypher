// =====================================================================
// CTI Agent — Neo4j STIX schema
// Run once via: cypher-shell -u neo4j -p cti_password_123 < schema.cypher
// =====================================================================

// Uniqueness constraints
CREATE CONSTRAINT threat_actor_id IF NOT EXISTS
  FOR (t:ThreatActor) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT malware_id IF NOT EXISTS
  FOR (m:Malware) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT tool_id IF NOT EXISTS
  FOR (t:Tool) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT technique_id IF NOT EXISTS
  FOR (t:Technique) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT tactic_id IF NOT EXISTS
  FOR (t:Tactic) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT vulnerability_id IF NOT EXISTS
  FOR (v:Vulnerability) REQUIRE v.id IS UNIQUE;
CREATE CONSTRAINT indicator_id IF NOT EXISTS
  FOR (i:Indicator) REQUIRE i.id IS UNIQUE;

// Indexes for name-based lookup (used by graph_query MCP tool)
CREATE INDEX threat_actor_name IF NOT EXISTS
  FOR (t:ThreatActor) ON (t.name);
CREATE INDEX malware_name IF NOT EXISTS
  FOR (m:Malware) ON (m.name);
CREATE INDEX tool_name IF NOT EXISTS
  FOR (t:Tool) ON (t.name);
CREATE INDEX technique_external_id IF NOT EXISTS
  FOR (t:Technique) ON (t.external_id);
