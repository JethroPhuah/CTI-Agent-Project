"""End-to-end ingestion pipeline.

Run as a script:
    python -m ingestion.pipeline
"""
from __future__ import annotations

import logging
import sys
from typing import List

from agents.config import get_settings

from .chunker import Chunk, chunk_document
from .embedder import embed_texts
from .rss_ingestor import CTIDocument, ingest_feeds
from .writers import write_chunks_to_milvus, write_docs_to_elasticsearch

log = logging.getLogger(__name__)


def docs_to_chunks(docs: List[CTIDocument]) -> List[Chunk]:
    chunks: List[Chunk] = []
    for d in docs:
        meta = {
            "doc_id": d.doc_id,
            "source": d.source,
            "url": d.url,
            "title": d.title,
            "published_at": d.published_at,
            "threat_actors": d.metadata.get("threat_actors", []),
            "malware": d.metadata.get("malware", []),
            "tools": d.metadata.get("tools", []),
        }
        chunks.extend(chunk_document(d.clean_text, meta))
    return chunks


def run(synthetic_fallback: bool = True) -> int:
    cfg = get_settings()

    log.info("Stage 1/4: pulling RSS feeds")
    docs = ingest_feeds(cfg.rss_feed_list, max_per_feed=20)

    if not docs and synthetic_fallback:
        log.warning("No live RSS docs — falling back to synthetic seed reports.")
        from scripts.generate_synthetic_reports import generate
        docs = generate()

    if not docs:
        log.error("No documents available; aborting.")
        return 1

    log.info("Stage 2/4: chunking %d documents", len(docs))
    chunks = docs_to_chunks(docs)
    log.info("  -> %d chunks", len(chunks))

    log.info("Stage 3/4: embedding %d chunks", len(chunks))
    embeddings = embed_texts(
        [c.text for c in chunks], model_name=cfg.embedding_model
    )

    log.info("Stage 4/4: writing to Milvus + Elasticsearch")
    write_chunks_to_milvus(
        chunks, embeddings,
        host=cfg.milvus_host, port=cfg.milvus_port,
        collection=cfg.milvus_collection, dim=cfg.embedding_dim,
    )
    write_docs_to_elasticsearch(
        docs,
        host=cfg.elasticsearch_host, port=cfg.elasticsearch_port,
        index=cfg.elasticsearch_index,
    )

    log.info("Ingestion complete: %d docs / %d chunks", len(docs), len(chunks))
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sys.exit(run())
