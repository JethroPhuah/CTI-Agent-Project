"""Validator agent -- checks the writer's answer against the evidence."""
import json
import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from .llm import get_llm
from .prompts import load as load_prompt
from .state import CTIState, trace_event
from .writer import _format_evidence

log = logging.getLogger(__name__)


def _parse_json(s: str) -> Dict[str, Any]:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    m = re.search(r"\{[\s\S]*\}", s)
    return json.loads(m.group(0) if m else s)


async def validator_node(state: CTIState) -> Dict[str, Any]:
    log.info("[validator] checking answer")
    trace = list(state.get("trace", []))
    trace.append(trace_event("validator", "start", {}))

    prompt = load_prompt("validator").format(
        user_query=state["user_query"],
        evidence=_format_evidence(state.get("evidence")),
        answer=state.get("answer", ""),
    )

    llm = get_llm(temperature=0.0)
    resp = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=state["user_query"]),
    ])
    raw = resp.content if hasattr(resp, "content") else str(resp)

    try:
        verdict = _parse_json(raw)
    except Exception:
        verdict = {"valid": True, "issues": [], "feedback": ""}

    if not isinstance(verdict.get("valid"), bool):
        verdict["valid"] = True

    trace.append(trace_event("validator", "final", verdict))
    retry_count = state.get("retry_count", 0) + (0 if verdict["valid"] else 1)
    log.info("[validator] valid=%s retry_count=%d", verdict["valid"], retry_count)
    return {"validation": verdict, "retry_count": retry_count, "trace": trace}
