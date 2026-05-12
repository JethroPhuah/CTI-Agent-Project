"""Retrieval MCP server.

Exposes four tools to the agent:
  * vector_search  . semantic search across CTI report chunks (Milvus)
  * keyword_search . BM25 search across full reports (Elasticsearch)
  * graph_query    . STIX knowledge graph lookups (Neo4j)
  * ioc_lookup     . IOC database lookup (Postgres)

To add a new retrieval tool, just write another function and decorate
it with `@registry.register()` and it will be discovered automatically.

NOTE on type annotations: FastMCP introspects parameter annotations
and (in some versions) does an `issubclass(annotation, Context)`
check that blows up on subscripted generics like `Optional[str]`.
For cross-version safety every TOOL parameter here uses bare classes
only (`str`, `int`, ...). Empty-string sentinels stand in for "not
provided" and are translated to `None` inside the function body.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from agents.config import get_settings
from databases.elasticsearch.client import ESClient
from databases.milvus.client import MilvusClient
from databases.neo4j.queries import GraphClient
from databases.postgres.client import PGClient
from ingestion.embedder import embed_query
from mcp_servers.common.registry import ToolRegistry

logging.basicConfig(level=logging.INFO, format="%(levelname)s [retrieval-mcp] %(message)s")
log = logging.getLogger(__name__)

cfg = get_settings()
mcp = FastMCP("cti-retrieval")
registry = ToolRegistry()

# Lazy clients (instantiated on first call so the server boots even
# if a downstream DB is still warming up.
_milvus: Optional[MilvusClient] = None
_es: Optional[ESClient] = None
_neo4j: Optional[GraphClient] = None
_pg: Optional[PGClient] = None


def _get_milvus() -> MilvusClient:
    global _milvus
    if _milvus is None:
        _milvus = MilvusClient(
            host=cfg.milvus_host, port=cfg.milvus_port,
            collection=cfg.milvus_collection,
        )
    return _milvus


def _get_es() -> ESClient:
    global _es
    if _es is None:
        _es = ESClient(
            host=cfg.elasticsearch_host, port=cfg.elasticsearch_port,
            index=cfg.elasticsearch_index,
        )
    return _es


def _get_neo4j() -> GraphClient:
    global _neo4j
    if _neo4j is None:
        _neo4j = GraphClient(
            uri=cfg.neo4j_uri, user=cfg.neo4j_user, password=cfg.neo4j_password,
        )
    return _neo4j


def _get_pg() -> PGClient:
    global _pg
    if _pg is None:
        _pg = PGClient(cfg.postgres_dsn)
    return _pg


# ---------------------------------------------------------------------
# Tools (bare-class param annotations only)
# ---------------------------------------------------------------------

@registry.register()
def vector_search(
    query: str,
    top_k: int = 5,
    threat_actor: str = "",
) -> list:
    """Semantic search across CTI report chunks using vector embeddings.

    Use this when the user asks free-form questions about threat
    intelligence content (e.g. "what do we know about APT41 cloud
    intrusions?"). Pass an empty `threat_actor` to skip filtering.
    """
    actor = threat_actor or None
    log.info("vector_search query=%r top_k=%d actor=%s", query, top_k, actor)
    vec = embed_query(query, model_name=cfg.embedding_model).tolist()
    return _get_milvus().search(vec, top_k=top_k, threat_actor=actor)


@registry.register()
def keyword_search(
    query: str,
    top_k: int = 10,
    threat_actor: str = "",
) -> list:
    """BM25 keyword search across full CTI reports in Elasticsearch.

    Use this for exact-match lookups (CVE IDs, IOCs, hash values, named
    tools/malware) where semantic similarity isn't the right model.
    Pass an empty `threat_actor` to skip filtering.
    """
    actor = threat_actor or None
    log.info("keyword_search query=%r actor=%s", query, actor)
    return _get_es().keyword_search(query, threat_actor=actor, size=top_k)


@registry.register()
def graph_query(
    entity_name: str,
    query_type: str = "uses",
    limit: int = 50,
) -> list:
    """STIX knowledge graph lookup over MITRE ATT&CK + ingested intel.

    query_type:
      * 'uses'        . what tools/malware/techniques does this actor use?
      * 'techniques'  . ATT&CK techniques associated with this actor
      * 'actors_using'. which actors use this tool/malware?
      * 'search'      . fuzzy entity name search
    """
    log.info("graph_query entity=%r type=%s", entity_name, query_type)
    g = _get_neo4j()
    if query_type == "uses":
        return g.actor_uses(entity_name, limit=limit)
    if query_type == "techniques":
        return g.techniques_of_actor(entity_name, limit=limit)
    if query_type == "actors_using":
        return g.actors_using_malware(entity_name, limit=limit)
    if query_type == "search":
        return g.search_entity(entity_name, limit=limit)
    return [{"error": f"unknown query_type: {query_type}"}]


@registry.register()
def ioc_lookup(
    value: str,
    ioc_type: str = "",
) -> list:
    """Look up an IOC (IP, domain, hash, URL, CVE) in the internal IOC database.

    Returns confidence, threat_level, tags, source, first_seen and any
    additional context. Use *before* calling external enrichment APIs to
    avoid burning external quota on already-known indicators. Pass an
    empty `ioc_type` to search across every type.
    """
    typ = ioc_type or None
    log.info("ioc_lookup value=%r type=%s", value, typ)
    rows = _get_pg().lookup_ioc(value, typ)
    # JSON-serialize datetimes / sets that the LLM tool channel can't handle.
    for r in rows:
        for k, v in list(r.items()):
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif isinstance(v, (set, frozenset)):
                r[k] = list(v)
    return rows


# ---------------------------------------------------------------------
# Wire registry -> FastMCP -> SSE
# ---------------------------------------------------------------------
attached = registry.attach_to(mcp)
log.info("retrieval-mcp ready: tools=%s", attached)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8101"))
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.run(transport="sse")
