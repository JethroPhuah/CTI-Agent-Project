"""FastAPI agent backend.

Endpoints:
  POST /chat         — SSE stream of agent steps + final answer
  POST /feedback     — record thumbs up/down for a run_id
  GET  /tools        — list MCP tools currently exposed (for UI toggles)
  GET  /history      — recent runs
  GET  /healthz      — liveness probe
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agents.config import get_settings
from agents.graph import build_graph, discover_tool_names
from databases.postgres.client import PGClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

cfg = get_settings()
app = FastAPI(title="CTI Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pg: Optional[PGClient] = None


def pg() -> PGClient:
    global _pg
    if _pg is None:
        _pg = PGClient(cfg.postgres_dsn)
    return _pg


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str
    selected_tools: List[str] = []


class FeedbackRequest(BaseModel):
    run_id: str
    rating: int   # +1 or -1
    comment: str = ""
    user_email: str = ""


# ----------------------------------------------------------------------
# /healthz
# ----------------------------------------------------------------------

@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"ok": True, "ts": time.time()}


# ----------------------------------------------------------------------
# /tools — let the UI know what tool toggles to render
# ----------------------------------------------------------------------

@app.get("/tools")
async def list_tools() -> Dict[str, Any]:
    names = await discover_tool_names()
    categorised: Dict[str, List[str]] = {
        "retrieval": [],
        "search": [],
        "enrichment": [],
        "other": [],
    }
    # Heuristic categorisation by name prefix — works because each MCP
    # server's tools have distinct names.
    for n in names:
        if n in {"vector_search", "keyword_search", "graph_query", "ioc_lookup"}:
            categorised["retrieval"].append(n)
        elif n.startswith("tavily"):
            categorised["search"].append(n)
        elif n.endswith("_lookup") or n == "enrich_all":
            categorised["enrichment"].append(n)
        else:
            categorised["other"].append(n)
    return {"tools": names, "categorised": categorised}


# ----------------------------------------------------------------------
# /chat — SSE stream
# ----------------------------------------------------------------------

@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(400, "empty query")

    run_id = str(uuid.uuid4())

    try:
        pg().create_run(req.query, req.selected_tools)
    except Exception as e:  # noqa: BLE001
        log.warning("could not record run start: %s", e)

    async def event_stream():
        started = time.time()
        graph = build_graph()
        available = await discover_tool_names()

        initial = {
            "user_query": req.query,
            "selected_tools": req.selected_tools,
            "available_tools": available,
            "evidence": [],
            "answer": "",
            "trace": [],
            "retry_count": 0,
            "run_id": run_id,
        }

        # Emit run_id immediately so the UI can attach feedback to it
        yield {"event": "run_started",
               "data": json.dumps({"run_id": run_id, "available_tools": available})}

        last_state: Dict[str, Any] = {}
        try:
            async for chunk in graph.astream(initial, stream_mode="updates"):
                # `chunk` is {node_name: state_delta}
                for node_name, delta in chunk.items():
                    last_state.update(delta)
                    payload = _step_payload(node_name, delta)
                    yield {"event": "agent_step", "data": json.dumps(payload)}

            duration = int((time.time() - started) * 1000)
            answer = last_state.get("answer", "(no answer produced)")
            yield {"event": "final",
                   "data": json.dumps({"run_id": run_id,
                                       "answer": answer,
                                       "duration_ms": duration,
                                       "validation": last_state.get("validation")})}
            try:
                pg().complete_run(run_id, answer, duration, "completed")
            except Exception as e:  # noqa: BLE001
                log.warning("could not record run completion: %s", e)

        except Exception as e:  # noqa: BLE001
            log.exception("graph failed")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            try:
                pg().complete_run(run_id, f"ERROR: {e}", 0, "failed")
            except Exception:  # noqa: BLE001
                pass

    return EventSourceResponse(event_stream())


def _step_payload(node_name: str, delta: Dict[str, Any]) -> Dict[str, Any]:
    """Compact + safe-to-serialize payload for the UI."""
    out: Dict[str, Any] = {"node": node_name}

    # Lift trace events
    trace = delta.get("trace") or []
    if trace:
        out["trace"] = trace[-3:]  # last few events for this node

    if node_name == "orchestrator" and "plan" in delta:
        out["plan"] = delta["plan"]
    if node_name == "retrieval" and "evidence" in delta:
        out["evidence_count"] = len(delta["evidence"])
        out["evidence_preview"] = [
            {"source": e.get("source"), "summary": e.get("summary")}
            for e in delta["evidence"][:6]
        ]
    if node_name == "writer" and "answer" in delta:
        out["answer_preview"] = delta["answer"][:300]
    if node_name == "validator" and "validation" in delta:
        out["validation"] = delta["validation"]
    return out


# ----------------------------------------------------------------------
# /feedback
# ----------------------------------------------------------------------

@app.post("/feedback")
async def feedback(req: FeedbackRequest) -> Dict[str, Any]:
    if req.rating not in (-1, 1):
        raise HTTPException(400, "rating must be -1 or 1")
    fb_id = pg().record_feedback(req.run_id, req.rating, req.comment, req.user_email)
    return {"feedback_id": fb_id, "stats": pg().feedback_stats()}


# ----------------------------------------------------------------------
# /history
# ----------------------------------------------------------------------

@app.get("/history")
async def history(limit: int = 20) -> Dict[str, Any]:
    with pg().conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT id, user_query, status, started_at, duration_ms, "
                "       LEFT(coalesce(final_answer,''), 200) AS preview "
                "FROM agent_runs ORDER BY started_at DESC LIMIT %s",
                [limit],
            )
            rows = cur.fetchall()
    for r in rows:
        for k, v in list(r.items()):
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return {"runs": rows}
