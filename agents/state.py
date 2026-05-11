"""Shared LangGraph state.

Every node receives + returns this TypedDict. Each node appends its trace
event to `trace` so the FastAPI layer can stream it to the UI.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, TypedDict


class TraceEvent(TypedDict, total=False):
    agent: str          # orchestrator | retrieval | writer | validator
    phase: str          # start | thought | action | observation | final | error
    content: Any
    timestamp: float


class CTIState(TypedDict, total=False):
    # Input
    user_query: str
    selected_tools: List[str]
    available_tools: List[str]   # filled in by graph startup

    # Orchestrator output
    plan: Dict[str, Any]         # {intent, writer_template, tools_to_use, entities, rationale}

    # Retrieval output
    evidence: List[Dict[str, Any]]

    # Writer output
    answer: str

    # Validator output
    validation: Dict[str, Any]   # {valid, issues, feedback}
    retry_count: int

    # Run metadata + transparency
    run_id: str
    trace: List[TraceEvent]
    started_at: float


def now() -> float:
    return time.time()


def trace_event(agent: str, phase: str, content: Any) -> TraceEvent:
    return {"agent": agent, "phase": phase, "content": content, "timestamp": now()}
