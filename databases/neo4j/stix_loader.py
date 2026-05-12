"""STIX 2.1 bundle loader for Neo4j.

Maps STIX SDOs/SROs to Neo4j nodes/edges:

  intrusion-set      -> :ThreatActor
  malware            -> :Malware
  tool               -> :Tool
  attack-pattern     -> :Technique
  x-mitre-tactic     -> :Tactic
  vulnerability      -> :Vulnerability
  indicator          -> :Indicator

  relationship.relationship_type becomes the edge type. Common types
  in MITRE ATT&CK: uses, mitigates, attributed-to, targets, subtechnique-of.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Dict, Iterable, Tuple

from neo4j import GraphDatabase

log = logging.getLogger(__name__)

MITRE_ATTACK_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)

STIX_TYPE_TO_LABEL = {
    "intrusion-set": "ThreatActor",
    "threat-actor": "ThreatActor",
    "malware": "Malware",
    "tool": "Tool",
    "attack-pattern": "Technique",
    "x-mitre-tactic": "Tactic",
    "vulnerability": "Vulnerability",
    "indicator": "Indicator",
    "campaign": "Campaign",
}


def _safe(s: str) -> str:
    """Cypher-safe edge type; relationship_type comes verbatim from STIX."""
    return s.replace("-", "_").upper()


def _external_id(obj: dict) -> str:
    for ref in obj.get("external_references", []) or []:
        if ref.get("source_name", "").startswith("mitre-"):
            return ref.get("external_id", "")
    return ""


def fetch_attack_bundle(cache_path: str = "./data/mitre_attack.json") -> dict:
    """Download MITRE ATT&CK bundle, caching to disk."""
    if os.path.exists(cache_path):
        log.info("Using cached ATT&CK bundle: %s", cache_path)
        with open(cache_path) as f:
            return json.load(f)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    log.info("Downloading MITRE ATT&CK STIX bundle ...")
    with urllib.request.urlopen(MITRE_ATTACK_URL, timeout=60) as r:
        data = json.loads(r.read())
    with open(cache_path, "w") as f:
        json.dump(data, f)
    log.info("Cached %d STIX objects.", len(data.get("objects", [])))
    return data


def _iter_sdo_sro(bundle: dict) -> Iterable[dict]:
    for obj in bundle.get("objects", []):
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        yield obj


def load_into_neo4j(
    bundle: dict,
    *,
    uri: str,
    user: str,
    password: str,
):
    """Idempotent load via MERGE."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    sdo_count = 0
    sro_count = 0

    with driver.session() as session:
        # Pass 1: nodes
        for obj in _iter_sdo_sro(bundle):
            stix_type = obj.get("type")
            label = STIX_TYPE_TO_LABEL.get(stix_type)
            if not label:
                continue

            props = {
                "id": obj["id"],
                "stix_type": stix_type,
                "name": obj.get("name", ""),
                "description": (obj.get("description") or "")[:4000],
                "external_id": _external_id(obj),
                "aliases": obj.get("aliases", []) or obj.get("x_mitre_aliases", []) or [],
                "created": obj.get("created", ""),
                "modified": obj.get("modified", ""),
            }

            cypher = (
                f"MERGE (n:{label} {{id: $id}}) "
                "SET n += $props"
            )
            session.run(cypher, id=props["id"], props=props)
            sdo_count += 1

        log.info("Loaded %d nodes", sdo_count)

        # Pass 2: relationships
        for obj in _iter_sdo_sro(bundle):
            if obj.get("type") != "relationship":
                continue
            src = obj.get("source_ref")
            dst = obj.get("target_ref")
            rtype = _safe(obj.get("relationship_type", "RELATED_TO"))
            if not (src and dst):
                continue

            cypher = (
                "MATCH (a {id: $src}), (b {id: $dst}) "
                f"MERGE (a)-[r:{rtype}]->(b) "
                "SET r.description = $desc"
            )
            session.run(
                cypher,
                src=src, dst=dst,
                desc=(obj.get("description") or "")[:1000],
            )
            sro_count += 1

        log.info("Loaded %d relationships", sro_count)

    driver.close()
    return {"nodes": sdo_count, "relationships": sro_count}


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from agents.config import get_settings
    cfg = get_settings()

    bundle = fetch_attack_bundle()
    counts = load_into_neo4j(
        bundle,
        uri=cfg.neo4j_uri,
        user=cfg.neo4j_user,
        password=cfg.neo4j_password,
    )
    log.info("Done: %s", counts)


if __name__ == "__main__":
    main()
