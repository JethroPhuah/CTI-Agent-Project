"""Thin Milvus client used by the retrieval MCP server."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

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
        threat_actor: str | None = None,
    ) -> List[Dict[str, Any]]:
        expr = None
        if threat_actor:
            expr = f'threat_actors like "%{threat_actor}%"'

        results = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"ef": 64}},
            limit=top_k,
            expr=expr,
            output_fields=[
                "chunk_id", "doc_id", "source", "url", "title",
                "published_at", "threat_actors", "malware", "text",
            ],
        )

        out = []
        for hits in results:
            for hit in hits:
                e = hit.entity
                out.append({
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
                })
        return out


def _safe_json(s: str) -> list:
    if not s:
        return []
    try:
        return json.loads(s)
    except Exception:
        return []
