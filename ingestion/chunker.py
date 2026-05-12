"""Sentence-aware chunker that preserves paragraph boundaries.

Each chunk carries the metadata of the parent document plus chunk-local
fields (chunk_id, char_start, char_end, token_count).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Iterable, List

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    token_count: int
    char_start: int
    char_end: int
    metadata: dict = field(default_factory=dict)


def _split_sentences(text: str) -> List[str]:
    # Lightweight sentence split that is good enough for security articles.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_document(
    text: str,
    metadata: dict,
    *,
    target_tokens: int = 400,
    overlap_tokens: int = 60,
) -> List[Chunk]:
    """Split `text` into Chunks of roughly `target_tokens`, with overlap.

    Each Chunk inherits `metadata` and gets a unique chunk_id.
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)
    chunks: List[Chunk] = []
    buf: List[str] = []
    buf_tokens = 0
    char_cursor = 0
    char_start = 0

    def _flush():
        nonlocal buf, buf_tokens, char_start, char_cursor
        if not buf:
            return
        chunk_text = " ".join(buf).strip()
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                text=chunk_text,
                token_count=len(_ENCODING.encode(chunk_text)),
                char_start=char_start,
                char_end=char_start + len(chunk_text),
                metadata={**metadata, "chunk_index": len(chunks)},
            )
        )

    for sent in sentences:
        sent_tokens = len(_ENCODING.encode(sent))
        if buf_tokens + sent_tokens > target_tokens and buf:
            _flush()
            # Build overlap from tail of previous buffer
            overlap_sents: List[str] = []
            overlap_count = 0
            for s in reversed(buf):
                t = len(_ENCODING.encode(s))
                if overlap_count + t > overlap_tokens:
                    break
                overlap_sents.insert(0, s)
                overlap_count += t
            buf = overlap_sents
            buf_tokens = overlap_count
            char_start = char_cursor

        buf.append(sent)
        buf_tokens += sent_tokens
        char_cursor += len(sent) + 1

    _flush()
    return chunks
