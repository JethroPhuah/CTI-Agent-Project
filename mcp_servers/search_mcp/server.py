"""Search MCP server (Tavily web search).

Hybrid mode: real Tavily API if TAVILY_API_KEY is set, otherwise returns
realistic synthetic search results so the demo always works.
"""

import logging
import os
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from agents.config import get_settings
from mcp_servers.common.registry import ToolRegistry

logging.basicConfig(level=logging.INFO, format="%(levelname)s [search-mcp] %(message)s")
log = logging.getLogger(__name__)

cfg = get_settings()
mcp = FastMCP("cti-search")
registry = ToolRegistry()


def _mock_tavily(query: str) -> List[Dict[str, Any]]:
    """Deterministic stand-in for Tavily so demos work without an API key."""
    base_results = [
        {
            "title": f"Threat report mentioning '{query}'",
            "url": "https://thehackernews.com/synthetic-result-1",
            "content": (
                f"Recent reporting indicates activity related to '{query}'. "
                "Multiple vendors have published indicators including domains, "
                "IP addresses, and file hashes. (Synthetic result, set "
                "TAVILY_API_KEY to use the real API.)"
            ),
            "score": 0.91,
        },
        {
            "title": f"CISA advisory referencing '{query}'",
            "url": "https://www.cisa.gov/synthetic-result-2",
            "content": (
                f"CISA, FBI, and NSA have issued a joint advisory regarding "
                f"'{query}'. The advisory contains TTPs aligned with MITRE "
                "ATT&CK and recommended mitigations."
            ),
            "score": 0.87,
        },
        {
            "title": f"Vendor blog: deep dive on '{query}'",
            "url": "https://www.mandiant.com/synthetic-result-3",
            "content": (
                f"Technical analysis of '{query}' including tooling overlap "
                "with previously tracked intrusion sets and observed "
                "infrastructure patterns."
            ),
            "score": 0.83,
        },
    ]
    return base_results


@registry.register()
def tavily_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search the open web for current threat intelligence using Tavily.

    Returns a structured list of results with title, url, content snippet
    and relevance score. Use this when the user asks about recent
    incidents, news, or anything that may post-date our internal corpus.
    """
    log.info("tavily_search query=%r", query)
    api_key = cfg.tavily_api_key or os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        log.info("  (no API key set, returning mock results)")
        return {"query": query, "mode": "mock", "results": _mock_tavily(query)[:max_results]}

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        resp = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )
        return {
            "query": query,
            "mode": "live",
            "answer": resp.get("answer", ""),
            "results": [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "content": r.get("content"),
                    "score": r.get("score"),
                }
                for r in resp.get("results", [])
            ],
        }
    except Exception as e:  # noqa: BLE001
        log.error("Tavily failed (%s); falling back to mock", e)
        return {"query": query, "mode": "mock_fallback", "results": _mock_tavily(query)[:max_results]}


attached = registry.attach_to(mcp)
log.info("search-mcp ready: tools=%s", attached)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8102"))
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.run(transport="sse")
