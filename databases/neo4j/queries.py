"""Reusable Cypher query helpers for the retrieval MCP server."""
from __future__ import annotations

from typing import Any, Dict, List

from neo4j import GraphDatabase


class GraphClient:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    # ------------------------------------------------------------------
    # Common queries used by the agent
    # ------------------------------------------------------------------

    def actor_uses(self, actor_name: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        """What tools/malware/techniques does this actor use?"""
        cypher = """
        MATCH (a:ThreatActor)
        WHERE toLower(a.name) = toLower($name)
           OR any(alias IN a.aliases WHERE toLower(alias) = toLower($name))
        MATCH (a)-[:USES]->(target)
        RETURN labels(target)[0] AS type,
               target.name AS name,
               target.external_id AS external_id,
               coalesce(target.description, "") AS description
        LIMIT $limit
        """
        return self._run(cypher, {"name": actor_name, "limit": limit})

    def techniques_of_actor(self, actor_name: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        cypher = """
        MATCH (a:ThreatActor)
        WHERE toLower(a.name) = toLower($name)
           OR any(alias IN a.aliases WHERE toLower(alias) = toLower($name))
        MATCH (a)-[:USES]->(t:Technique)
        RETURN t.name AS name, t.external_id AS technique_id,
               coalesce(t.description, "") AS description
        LIMIT $limit
        """
        return self._run(cypher, {"name": actor_name, "limit": limit})

    def actors_using_malware(self, malware_name: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        cypher = """
        MATCH (m)
        WHERE (m:Malware OR m:Tool)
          AND toLower(m.name) = toLower($name)
        MATCH (a:ThreatActor)-[:USES]->(m)
        RETURN a.name AS actor, a.aliases AS aliases,
               coalesce(a.description, "") AS description
        LIMIT $limit
        """
        return self._run(cypher, {"name": malware_name, "limit": limit})

    def search_entity(self, query: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        """Fuzzy name search across all entity types."""
        cypher = """
        MATCH (n)
        WHERE (n:ThreatActor OR n:Malware OR n:Tool OR n:Technique
               OR n:Vulnerability OR n:Campaign)
          AND (toLower(n.name) CONTAINS toLower($q)
               OR any(a IN coalesce(n.aliases, []) WHERE toLower(a) CONTAINS toLower($q)))
        RETURN labels(n)[0] AS type, n.name AS name,
               n.external_id AS external_id,
               coalesce(n.description, "") AS description
        LIMIT $limit
        """
        return self._run(cypher, {"q": query, "limit": limit})

    def custom_cypher(self, cypher: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        return self._run(cypher, params or {})

    # ------------------------------------------------------------------

    def _run(self, cypher: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]
