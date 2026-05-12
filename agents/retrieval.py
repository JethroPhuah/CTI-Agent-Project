"""Retrieval agent: ReACT loop over MCP tools.

Implementation note: rather than rolling our own ReACT parser, we use
LangGraph's prebuilt `create_react_agent`, which already handles the
Thought/Action/Observation loop and integrates cleanly with our
LangChain BaseTool list (loaded from MCP servers).

We then translate the agent's intermediate `tool_calls` into our
own trace format so the UI can show step-by-step.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from .llm import get_llm
from .prompts import load as load_prompt
from .state import CTIState, trace_event
from .tools.mcp_loader import filter_tools, load_all_tools

log = logging.getLogger(__name__)


def _evidence_from_messages(messages) -> List[Dict[str, Any]]:
    """Extract tool calls + responses from a message list and map them to
    our `evidence` schema."""
    evidence: List[Dict[str, Any]] = []
    pending: Dict[str, Dict[str, Any]] = {}

    for msg in messages:
        # AIMessage with tool_calls
        tcs = getattr(msg, "tool_calls", None) or []
        for tc in tcs:
            pending[tc["id"]] = {
                "tool": tc["name"],
                "args": tc.get("args", {}),
            }
        # ToolMessage
        if msg.__class__.__name__ == "ToolMessage":
            tc_id = getattr(msg, "tool_call_id", None)
            entry = pending.pop(tc_id, {"tool": "?", "args": {}})
            payload = msg.content
            try:
                payload = json.loads(payload) if isinstance(payload, str) else payload
            except Exception:
                pass
            evidence.append({
                "source": entry["tool"],
                "summary": _summarize(payload),
                "args": entry["args"],
                "payload": payload,
            })
    return evidence


def _summarize(payload: Any) -> str:
    if isinstance(payload, list):
        return f"{len(payload)} record(s)"
    if isinstance(payload, dict):
        keys = list(payload.keys())[:5]
        return f"keys={keys}"
    s = str(payload)
    return s[:160] + ("…" if len(s) > 160 else "")


async def retrieval_node(state: CTIState) -> Dict[str, Any]:
    log.info("[retrieval] starting ReACT loop")
    trace = list(state.get("trace", []))
    trace.append(trace_event("retrieval", "start", {"plan": state.get("plan")}))

    # 1. Load every MCP tool, filter by orchestrator's tools_to_use
    all_tools = await load_all_tools()
    plan_tools = state.get("plan", {}).get("tools_to_use") or None
    tools = filter_tools(all_tools, plan_tools)
    if not tools:
        tools = all_tools  # fail open
    trace.append(trace_event("retrieval", "thought",
                             f"using {len(tools)} tools: {[t.name for t in tools]}"))

    # 2. Build the ReACT agent with our system prompt
    system_prompt = load_prompt("retrieval_react").format(
        user_query=state["user_query"],
        plan=json.dumps(state.get("plan", {}), ensure_ascii=False),
    )

    react_agent = create_react_agent(
        get_llm(temperature=0.0),
        tools,
        prompt=system_prompt,
    )

    # 3. Invoke, capturing all messages for trace extraction
    result = await react_agent.ainvoke(
        {"messages": [HumanMessage(content=state["user_query"])]},
        config={"recursion_limit": 12},
    )
    messages = result.get("messages", [])

    # 4. Translate tool calls into our trace + evidence
    for msg in messages:
        for tc in (getattr(msg, "tool_calls", None) or []):
            trace.append(trace_event("retrieval", "action",
                                     {"tool": tc["name"], "args": tc.get("args", {})}))
        if msg.__class__.__name__ == "ToolMessage":
            trace.append(trace_event("retrieval", "observation",
                                     {"tool_call_id": getattr(msg, "tool_call_id", None),
                                      "content": _summarize(msg.content)}))

    evidence = _evidence_from_messages(messages)
    trace.append(trace_event("retrieval", "final",
                             {"evidence_count": len(evidence)}))
    log.info("[retrieval] gathered %d evidence items", len(evidence))
    return {"evidence": evidence, "trace": trace}
