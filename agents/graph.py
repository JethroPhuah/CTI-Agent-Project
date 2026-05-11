"""LangGraph wiring.

Flow:
   START -> orchestrator -> retrieval -> writer -> validator
                                                    |
                                       (invalid && retries < max)
                                                    |
                                                 writer ...

After validation succeeds (or retries exhausted) -> END.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List

from langgraph.graph import END, START, StateGraph

from .config import get_settings
from .orchestrator import orchestrator_node
from .retrieval import retrieval_node
from .state import CTIState
from .tools.mcp_loader import load_all_tools
from .validator import validator_node
from .writer import writer_node

log = logging.getLogger(__name__)


def _route_after_validator(state: CTIState):
    cfg = get_settings()
    v = state.get("validation") or {}
    if v.get("valid", True):
        return END
    if state.get("retry_count", 0) >= cfg.max_validation_retries:
        return END
    return "writer"


def build_graph():
    g = StateGraph(CTIState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("retrieval", retrieval_node)
    g.add_node("writer", writer_node)
    g.add_node("validator", validator_node)

    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "retrieval")
    g.add_edge("retrieval", "writer")
    g.add_edge("writer", "validator")
    g.add_conditional_edges(
        "validator",
        _route_after_validator,
        {"writer": "writer", END: END},
    )
    return g.compile()


# ----------------------------------------------------------------------
# Convenience entry points
# ----------------------------------------------------------------------

async def discover_tool_names() -> List[str]:
    try:
        tools = await load_all_tools()
        return [t.name for t in tools]
    except Exception as e:  # noqa: BLE001
        log.warning("MCP discovery failed: %s", e)
        return []


async def run_query(
    user_query: str,
    selected_tools: List[str] | None = None,
    run_id: str = "",
) -> Dict[str, Any]:
    """Run a single query end-to-end and return the final state."""
    graph = build_graph()
    available = await discover_tool_names()
    initial: CTIState = {
        "user_query": user_query,
        "selected_tools": selected_tools or [],
        "available_tools": available,
        "evidence": [],
        "answer": "",
        "trace": [],
        "retry_count": 0,
        "run_id": run_id,
    }
    final = await graph.ainvoke(initial)
    return final


async def stream_query(
    user_query: str,
    selected_tools: List[str] | None = None,
    run_id: str = "",
) -> AsyncIterator[Dict[str, Any]]:
    """Stream incremental state updates — used by the FastAPI SSE endpoint."""
    graph = build_graph()
    available = await discover_tool_names()
    initial: CTIState = {
        "user_query": user_query,
        "selected_tools": selected_tools or [],
        "available_tools": available,
        "evidence": [],
        "answer": "",
        "trace": [],
        "retry_count": 0,
        "run_id": run_id,
    }
    async for chunk in graph.astream(initial, stream_mode="updates"):
        yield chunk
