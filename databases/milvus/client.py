"""Thin Milvus client used by the retrieval MCP server.

Note on filtering: we deliberately do NOT push threat_actor filters
down to Milvus. Milvus 2.4's expression parser rejects leading-wildcard
`LIKE` patterns ("failed to create query plan") and the field stores
threat_actors as a JSON-encoded list, which makes server-side filtering
brittle across Milvus versions.

Instead we over-fetch and post-filter in Python. The embedding ranking
already pulls threat-actor-relevant chunks to the top, so post-filtering
only acts as a soft re-rank when the agent passes a specific actor name.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from pymilvus import Collection, connections

log = logging.getLogger(__name__)


class MilvusClient:
    def __init__(self, host: str, port: int, collection: str):
        connections.connect(alias="default", host=host, port=str(port))
        self.collection = Collection(collection)
        self.collection.load()

    def search(
        self,
        query_vector: List[float],
        *,
        top_k: int = 5,
        threat_actor: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # Over-fetch when a soft filter is requested, then trim after
        # post-filtering. Keep the upper bound modest to stay snappy.
        limit = top_k * 4 if threat_actor else top_k
        limit = min(limit, 50)

        results = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=limit,
            output_fields=[
                "chunk_id", "doc_id", "source", "url", "title",
                "published_at", "threat_actors", "malware", "text",
            ],
        )

        out: List[Dict[str, Any]] = []
        for hits in results:
            for hit in hits:
                e = hit.entity
                row = {
                    "chunk_id": e.get("chunk_id"),
                    "doc_id": e.get("doc_id"),
                    "score": float(hit.score),
                    "source": e.get("source"),
                    "url": e.get("url"),
                    "title": e.get("title"),
                    "published_at": e.get("published_at"),
                    "threat_actors": _safe_json(e.get("threat_actors")),
                    "malware": _safe_json(e.get("malware")),
                    "text": e.get("text"),
                }
                out.append(row)

        if threat_actor:
            needle = threat_actor.lower()
            preferred = [
                r for r in out
                if any(needle in a.lower() for a in r.get("threat_actors", []))
                or needle in (r.get("text") or "").lower()
                or needle in (r.get("title") or "").lower()
            ]
            # Keep matched rows first, then fill with the rest until top_k.
            rest = [r for r in out if r not in preferred]
            out = (preferred + rest)[:top_k]
        else:
            out = out[:top_k]

        return out


def _safe_json(s: str) -> list:
    if not s:
        return []
    try:
        return json.loads(s)
    except Exception:
        return []
