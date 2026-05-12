"""Orchestrator agent: classifies the user intent and produces a routing plan."""
import json
import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from .llm import get_llm
from .prompts import load as load_prompt
from .state import CTIState, trace_event

log = logging.getLogger(__name__)


_VALID_TEMPLATES = {
    "summary", "threat_actor_profile", "ioc_report",
    "correlation", "general",
}


def _parse_json(s: str) -> Dict[str, Any]:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    m = re.search(r"\{[\s\S]*\}", s)
    return json.loads(m.group(0) if m else s)


async def orchestrator_node(state: CTIState) -> Dict[str, Any]:
    user_query = state["user_query"]
    selected = state.get("selected_tools") or []
    available = state.get("available_tools") or []

    log.info("[orchestrator] query=%r", user_query)
    trace = list(state.get("trace", []))
    trace.append(trace_event("orchestrator", "start", {"query": user_query}))

    prompt = load_prompt("orchestrator").format(
        user_query=user_query,
        available_tools=", ".join(available) or "(none discovered)",
        selected_tools=", ".join(selected) or "ALL",
    )

    llm = get_llm(temperature=0.0)
    # vLLM/Qwen3 chat template requires a user turn; without it we get
    # "No user query found in messages." HTTP 400.
    resp = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=user_query),
    ])
    raw = resp.content if hasattr(resp, "content") else str(resp)

    try:
        plan = _parse_json(raw)
    except Exception as e:  # noqa: BLE001
        log.warning("orchestrator JSON parse failed (%s); falling back", e)
        plan = {
            "intent": "general",
            "writer_template": "general",
            "tools_to_use": ["vector_search", "keyword_search"],
            "entities": {"threat_actors": [], "malware": [], "iocs": [], "cves": []},
            "rationale": "fallback: parse error",
        }

    if plan.get("writer_template") not in _VALID_TEMPLATES:
        plan["writer_template"] = "general"

    if selected:
        plan["tools_to_use"] = [t for t in plan.get("tools_to_use", []) if t in selected]

    trace.append(trace_event("orchestrator", "final", plan))
    log.info("[orchestrator] plan=%s", plan)
    return {"plan": plan, "trace": trace}
