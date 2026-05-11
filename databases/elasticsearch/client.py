"""Thin Elasticsearch client for the retrieval MCP server."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from elasticsearch import Elasticsearch

log = logging.getLogger(__name__)


class ESClient:
    def __init__(self, host: str, port: int, index: str):
        self.es = Elasticsearch(f"http://{host}:{port}")
        self.index = index

    def keyword_search(
        self,
        query: str,
        *,
        threat_actor: str | None = None,
        size: int = 10,
    ) -> List[Dict[str, Any]]:
        must: List[Dict[str, Any]] = [
            {"multi_match": {
                "query": query,
                "fields": ["title^2", "clean_text"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }}
        ]
        if threat_actor:
            must.append({"term": {"threat_actors": threat_actor}})

        body = {
            "query": {"bool": {"must": must}},
            "size": size,
            "_source": [
                "doc_id", "source", "url", "title",
                "published_at", "threat_actors", "malware",
            ],
            "highlight": {
                "fields": {"clean_text": {"fragment_size": 200, "number_of_fragments": 2}}
            },
        }
        try:
            res = self.es.search(index=self.index, body=body)
        except Exception as e:  # noqa: BLE001
            log.error("ES search failed: %s", e)
            return []

        hits = []
        for h in res.get("hits", {}).get("hits", []):
            src = h.get("_source", {})
            highlights = h.get("highlight", {}).get("clean_text", [])
            hits.append({
                "doc_id": src.get("doc_id"),
                "score": h.get("_score"),
                "source": src.get("source"),
                "url": src.get("url"),
                "title": src.get("title"),
                "published_at": src.get("published_at"),
                "threat_actors": src.get("threat_actors", []),
                "malware": src.get("malware", []),
                "snippets": highlights,
            })
        return hits
