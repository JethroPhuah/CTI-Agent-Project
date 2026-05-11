"""Embedding wrapper around sentence-transformers."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List

import numpy as np

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_model(model_name: str):
    from sentence_transformers import SentenceTransformer
    log.info("Loading embedding model: %s", model_name)
    return SentenceTransformer(model_name)


def embed_texts(texts: List[str], *, model_name: str) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = _get_model(model_name)
    vecs = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vecs.astype(np.float32)


def embed_query(query: str, *, model_name: str) -> np.ndarray:
    return embed_texts([query], model_name=model_name)[0]
