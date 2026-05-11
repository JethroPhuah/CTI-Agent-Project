"""Writers that persist chunks/docs to Milvus and Elasticsearch."""
from __future__ import annotations

import json
import logging
from typing import List

from elasticsearch import Elasticsearch, helpers
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from .chunker import Chunk
from .rss_ingestor import CTIDocument

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Milvus
# ----------------------------------------------------------------------

def _ensure_milvus_collection(name: str, dim: int) -> Collection:
    if utility.has_collection(name):
        return Collection(name)

    schema = CollectionSchema(
        fields=[
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR,
                        max_length=64, is_primary=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="published_at", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="threat_actors", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="malware", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=16384),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ],
        description="CTI report chunks with embeddings + metadata",
    )
    coll = Collection(name=name, schema=schema)
    coll.create_index(
        field_name="embedding",
        index_params={
            "metric_type": "IP",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200},
        },
    )
    log.info("Created Milvus collection %s", name)
    return coll


def write_chunks_to_milvus(
    chunks: List[Chunk],
    embeddings,
    *,
    host: str,
    port: int,
    collection: str,
    dim: int,
):
    if not chunks:
        return
    connections.connect(alias="default", host=host, port=port)
    coll = _ensure_milvus_collection(collection, dim)

    rows = {
        "chunk_id": [c.chunk_id for c in chunks],
        "doc_id": [c.metadata.get("doc_id", "") for c in chunks],
        "source": [c.metadata.get("source", "")[:255] for c in chunks],
        "url": [c.metadata.get("url", "")[:2047] for c in chunks],
        "title": [c.metadata.get("title", "")[:1023] for c in chunks],
        "published_at": [c.metadata.get("published_at", "")[:63] for c in chunks],
        "threat_actors": [
            json.dumps(c.metadata.get("threat_actors", []))[:2047] for c in chunks
        ],
        "malware": [
            json.dumps(c.metadata.get("malware", []))[:2047] for c in chunks
        ],
        "text": [c.text[:16383] for c in chunks],
        "embedding": embeddings.tolist(),
    }
    coll.insert(list(rows.values()))
    coll.flush()
    coll.load()
    log.info("Inserted %d chunks into Milvus.%s", len(chunks), collection)


# ----------------------------------------------------------------------
# Elasticsearch
# ----------------------------------------------------------------------

def _ensure_es_index(es: Elasticsearch, name: str):
    if es.indices.exists(index=name):
        return
    es.indices.create(
        index=name,
        body={
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "title": {"type": "text"},
                    "published_at": {"type": "date"},
                    "clean_text": {"type": "text"},
                    "threat_actors": {"type": "keyword"},
                    "malware": {"type": "keyword"},
                    "tools": {"type": "keyword"},
                    "iocs": {"type": "object", "enabled": True},
                }
            }
        },
    )
    log.info("Created ES index %s", name)


def write_docs_to_elasticsearch(
    docs: List[CTIDocument],
    *,
    host: str,
    port: int,
    index: str,
):
    if not docs:
        return
    es = Elasticsearch(f"http://{host}:{port}")
    _ensure_es_index(es, index)

    actions = []
    for d in docs:
        actions.append({
            "_index": index,
            "_id": d.doc_id,
            "_source": {
                "doc_id": d.doc_id,
                "source": d.source,
                "url": d.url,
                "title": d.title,
                "published_at": d.published_at,
                "clean_text": d.clean_text,
                "threat_actors": d.metadata.get("threat_actors", []),
                "malware": d.metadata.get("malware", []),
                "tools": d.metadata.get("tools", []),
                "iocs": d.metadata.get("iocs", {}),
            }
        })
    helpers.bulk(es, actions)
    log.info("Inserted %d docs into ES index %s", len(docs), index)
