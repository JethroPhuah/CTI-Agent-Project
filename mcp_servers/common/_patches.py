"""Cross-version defensive patches for FastMCP.

Older versions of `mcp.server.fastmcp.tools.base.Tool.from_function`
do this:

    for param_name, param in sig.parameters.items():
        if issubclass(param.annotation, Context):
            context_kwarg = param_name
            break

When `param.annotation` is anything other than a real class (e.g. a
typing generic like `Optional[str]`, or a string left over from PEP 563
deferred evaluation), `issubclass()` raises `TypeError`. Newer mcp
versions wrap this in `isinstance(annotation, type)` first.

This module monkey-patches `Tool.from_function` to pre-resolve
`context_kwarg` defensively. The patch is idempotent and only applied
once per process. Importing this module before any tool registration
makes the agentic stack work on every mcp 1.x release.
"""
from __future__ import annotations

import inspect
import logging

log = logging.getLogger(__name__)


def apply() -> None:
    try:
        from mcp.server.fastmcp.tools import base as _base
        from mcp.server.fastmcp import Context as _Context
    except Exception as e:  # noqa: BLE001
        log.debug("FastMCP not importable, skipping patch: %s", e)
        return

    if getattr(_base, "_cti_agent_patched", False):
        return

    _orig = _base.Tool.from_function

    @classmethod
    def _safe_from_function(  # type: ignore[misc]
        cls, fn, name=None, description=None, context_kwarg=None, **extra
    ):
        if context_kwarg is None:
            try:
                sig = inspect.signature(fn)
                for pname, p in sig.parameters.items():
                    ann = p.annotation
                    if not isinstance(ann, type):
                        continue
                    try:
                        if issubclass(ann, _Context):
                            context_kwarg = pname
                            break
                    except TypeError:
                        continue
            except (ValueError, TypeError):
                pass
            # Sentinel: anything not-None skips the original buggy loop.
            # Empty string is the conventional "no context arg" marker
            # used by recent FastMCP versions internally.
            if context_kwarg is None:
                context_kwarg = ""

        # Forward to the original, accepting whatever extra kwargs newer
        # FastMCP versions may have added to from_function.
        try:
            return _orig.__func__(cls, fn, name, description, context_kwarg, **extra)
        except TypeError:
            # Older signature didn't have **extra
            return _orig.__func__(cls, fn, name, description, context_kwarg)

    _base.Tool.from_function = _safe_from_function
    _base._cti_agent_patched = True
    log.info("FastMCP Tool.from_function patched for cross-version safety")


# Auto-apply on import
apply()
