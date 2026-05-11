"""Writer agent -- selects a one-shot prompt template based on the
orchestrator's plan and produces the final answer."""
import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from .llm import get_llm
from .prompts import load as load_prompt
from .state import CTIState, trace_event

log = logging.getLogger(__name__)


_TEMPLATE_MAP = {
    "summary": "writer_summary",
    "threat_actor_profile": "writer_threat_actor",
    "ioc_report": "writer_ioc_report",
    "correlation": "writer_correlation",
    "general": "writer_general",
}


def _format_evidence(evidence) -> str:
    return json.dumps(
        [
            {
                "source": e.get("source"),
                "summary": e.get("summary"),
                "payload": _trim(e.get("payload")),
            }
            for e in (evidence or [])
        ],
        ensure_ascii=False,
        indent=2,
    )


def _trim(p):
    s = json.dumps(p, default=str) if p is not None else ""
    if len(s) > 1500:
        return s[:1500] + "...<truncated>"
    return p


async def writer_node(state: CTIState) -> Dict[str, Any]:
    plan = state.get("plan", {}) or {}
    template_name = _TEMPLATE_MAP.get(plan.get("writer_template", "general"), "writer_general")
    log.info("[writer] using template=%s", template_name)

    trace = list(state.get("trace", []))
    trace.append(trace_event("writer", "start", {"template": template_name}))

    prompt = load_prompt(template_name).format(
        user_query=state["user_query"],
        evidence=_format_evidence(state.get("evidence")),
    )
    feedback = (state.get("validation") or {}).get("feedback")
    if feedback:
        prompt += f"\n\nThe previous attempt failed validation. Fix this: {feedback}"

    llm = get_llm(temperature=0.3)
    resp = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=state["user_query"]),
    ])
    answer = resp.content if hasattr(resp, "content") else str(resp)

    trace.append(trace_event("writer", "final",
                             {"chars": len(answer), "preview": answer[:200]}))
    log.info("[writer] produced %d chars", len(answer))
    return {"answer": answer, "trace": trace}
