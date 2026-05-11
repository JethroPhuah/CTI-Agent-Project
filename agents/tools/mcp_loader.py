"""Direct MCP-to-LangChain bridge.

Replaces the upstream `langchain-mcp-adapters` library, which couples
us tightly to a fast-moving langchain-core minor version.

We use only:
    * the `mcp` Python SDK (transport, sessions, tool calls)
    * pydantic (to build args_schema from MCP's JSON Schema)
    * langchain_core.tools.StructuredTool (the agent's expected interface)

For each call to `load_all_tools()` we:
    1. Open an SSE session per configured MCP server.
    2. List the tools the server exposes.
    3. For each tool, build a `StructuredTool` whose args_schema is a
       dynamically-created pydantic model derived from the tool's
       JSON Schema, and whose `coroutine` opens a fresh SSE session,
       calls the tool, parses the result, and returns it.

This means each tool invocation is independent (a new SSE session per
call). That's slightly more handshake overhead than a long-lived
session, but it keeps the implementation trivial and side-steps the
session-lifecycle bugs in older langchain-mcp-adapters.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel, Field, create_model

from agents.config import get_settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# JSON Schema -> Pydantic model
# ---------------------------------------------------------------------

_JSON_TO_PY = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _schema_to_pydantic(name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """Convert a (flat) JSON Schema object to a Pydantic model class."""
    properties = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])

    fields: Dict[str, Any] = {}
    for prop, definition in properties.items():
        py_type = _JSON_TO_PY.get(definition.get("type", "string"), str)
        description = definition.get("description", "")
        if prop in required and "default" not in definition:
            fields[prop] = (py_type, Field(..., description=description))
        else:
            default = definition.get("default", None)
            fields[prop] = (Optional[py_type], Field(default=default, description=description))

    if not fields:
        # StructuredTool requires *some* schema; an empty model is fine.
        return create_model(f"{name}_Args")
    return create_model(f"{name}_Args", **fields)


# ---------------------------------------------------------------------
# Per-server connection helper
# ---------------------------------------------------------------------

class MCPServer:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    async def list_tools(self) -> List[Any]:
        async with sse_client(self.url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resp = await session.list_tools()
                return list(resp.tools)

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        async with sse_client(self.url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                # MCP returns a CallToolResult with `content: [TextContent|...]`
                contents = getattr(result, "content", None) or []
                if contents:
                    first = contents[0]
                    text = getattr(first, "text", None)
                    if text is not None:
                        try:
                            return json.loads(text)
                        except (ValueError, TypeError):
                            return text
                return str(result)


# ---------------------------------------------------------------------
# Build LangChain StructuredTools
# ---------------------------------------------------------------------

def _make_structured_tool(server: MCPServer, tool_def: Any) -> StructuredTool:
    args_schema = _schema_to_pydantic(tool_def.name, tool_def.inputSchema or {})

    async def _ainvoke(**kwargs: Any) -> Any:
        # Drop None/empty defaults so MCP tools see the same shape they
        # declared (avoids surprising "passed null" issues).
        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        return await server.call_tool(tool_def.name, cleaned)

    return StructuredTool.from_function(
        coroutine=_ainvoke,
        name=tool_def.name,
        description=tool_def.description or f"Call MCP tool {tool_def.name}",
        args_schema=args_schema,
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def _servers() -> List[MCPServer]:
    cfg = get_settings()
    return [
        MCPServer("retrieval",  cfg.retrieval_mcp_url),
        MCPServer("search",     cfg.search_mcp_url),
        MCPServer("enrichment", cfg.enrichment_mcp_url),
    ]


async def load_all_tools() -> List[StructuredTool]:
    """Connect to every configured MCP server, list its tools, and return
    them as LangChain StructuredTools.
    """
    out: List[StructuredTool] = []
    for srv in _servers():
        try:
            tool_defs = await srv.list_tools()
        except Exception as e:  # noqa: BLE001
            log.warning("MCP %s discovery failed: %s", srv.name, e)
            continue
        for td in tool_defs:
            try:
                out.append(_make_structured_tool(srv, td))
            except Exception as e:  # noqa: BLE001
                log.warning("Skipping tool %s on %s: %s", td.name, srv.name, e)
    log.info("Loaded %d MCP tools: %s", len(out), [t.name for t in out])
    return out


def filter_tools(tools: List[StructuredTool], allow: Optional[List[str]]) -> List[StructuredTool]:
    if not allow:
        return tools
    s = set(allow)
    return [t for t in tools if t.name in s]
