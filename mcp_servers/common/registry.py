"""Tiny tool registry helper.

Lets each MCP server file define tools as plain Python functions decorated
with `@register("category")` and have them auto-registered with FastMCP.
This keeps the "add a new tool by dropping in one function" property the
user asked for.
"""
from __future__ import annotations

from typing import Callable, Dict, List


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str | None = None) -> Callable:
        def _wrap(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            if tool_name in self._tools:
                raise ValueError(f"duplicate tool: {tool_name}")
            self._tools[tool_name] = fn
            return fn
        return _wrap

    def attach_to(self, server) -> List[str]:
        """Bind every registered tool to a FastMCP server instance."""
        attached: List[str] = []
        for name, fn in self._tools.items():
            server.tool(name=name)(fn)
            attached.append(name)
        return attached

    def names(self) -> List[str]:
        return list(self._tools.keys())
