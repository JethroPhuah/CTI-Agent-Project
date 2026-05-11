"""Enrichment MCP server.

Exposes one tool per adapter (auto-generated from `adapters.ADAPTERS`),
plus an `enrich_all` aggregator. Adding a new provider only requires
adding a new EnrichmentAdapter subclass to adapters.py.
"""

import logging
import os
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from mcp_servers.common.registry import ToolRegistry
from mcp_servers.enrichment_mcp.adapters import ADAPTERS, get_adapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s [enrichment-mcp] %(message)s")
log = logging.getLogger(__name__)

mcp = FastMCP("cti-enrichment")
registry = ToolRegistry()


def _make_provider_tool(adapter):
    """Generate a per-provider MCP tool function dynamically."""

    def _tool(value: str, ioc_type: str) -> Dict[str, Any]:
        log.info("%s_lookup value=%r type=%s", adapter.name, value, ioc_type)
        return adapter.enrich(value, ioc_type)

    _tool.__name__ = f"{adapter.name}_lookup"
    _tool.__doc__ = (
        f"Enrich an IOC using {adapter.name}. ioc_type one of "
        "{ipv4, ipv6, domain, url, md5, sha1, sha256}. "
        "Returns reputation, threat score and provider-specific metadata."
    )
    return _tool


for adapter in ADAPTERS:
    registry.register(name=f"{adapter.name}_lookup")(_make_provider_tool(adapter))


@registry.register()
def enrich_all(value: str, ioc_type: str) -> List[Dict[str, Any]]:
    """Run all available enrichment providers against this IOC.

    Useful when the agent wants a multi-source consensus on an indicator.
    Returns a list of provider responses.
    """
    log.info("enrich_all value=%r type=%s", value, ioc_type)
    out = []
    for adapter in ADAPTERS:
        try:
            out.append(adapter.enrich(value, ioc_type))
        except Exception as e:  # noqa: BLE001
            out.append({"provider": adapter.name, "error": str(e)})
    return out


attached = registry.attach_to(mcp)
log.info("enrichment-mcp ready: tools=%s", attached)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8103"))
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.run(transport="sse")
