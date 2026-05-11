"""Pull articles from RSS feeds and emit normalized CTI documents.

A normalized doc has: id, source, url, title, published_at, raw_html,
clean_text, plus extractor-derived metadata (iocs/actors/malware/tools).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import feedparser
import trafilatura
from dateutil import parser as dateparser

from .extractors import extract_all

log = logging.getLogger(__name__)


@dataclass
class CTIDocument:
    doc_id: str
    source: str
    url: str
    title: str
    published_at: str  # ISO-8601
    clean_text: str
    metadata: dict = field(default_factory=dict)


def _hash_id(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def _parse_date(s: Optional[str]) -> str:
    if not s:
        return datetime.now(timezone.utc).isoformat()
    try:
        return dateparser.parse(s).astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def fetch_article_text(url: str) -> str:
    """Fetch + clean an article body. Returns empty string on failure."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
        )
        return text or ""
    except Exception as e:
        log.warning("trafilatura failed for %s: %s", url, e)
        return ""


def ingest_feed(feed_url: str, *, max_items: int = 25) -> List[CTIDocument]:
    """Parse a single RSS feed; return up to `max_items` normalized docs."""
    log.info("Fetching RSS feed: %s", feed_url)
    parsed = feedparser.parse(feed_url)
    source = parsed.feed.get("title", feed_url)

    docs: List[CTIDocument] = []
    for entry in parsed.entries[:max_items]:
        url = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not url or not title:
            continue

        # Prefer feed summary; fall back to fetching full article.
        body = entry.get("summary", "") or entry.get("description", "")
        if len(body) < 400:
            full = fetch_article_text(url)
            if full:
                body = full

        if not body or len(body) < 200:
            continue

        meta = extract_all(body)
        meta["feed"] = feed_url

        doc = CTIDocument(
            doc_id=_hash_id(url),
            source=source,
            url=url,
            title=title,
            published_at=_parse_date(entry.get("published")),
            clean_text=body,
            metadata=meta,
        )
        docs.append(doc)

    log.info("  -> got %d docs from %s", len(docs), source)
    return docs


def ingest_feeds(feed_urls: Iterable[str], *, max_per_feed: int = 25) -> List[CTIDocument]:
    out: List[CTIDocument] = []
    for url in feed_urls:
        try:
            out.extend(ingest_feed(url, max_items=max_per_feed))
        except Exception as e:  # noqa: BLE001
            log.error("Feed %s failed: %s", url, e)
    return out
