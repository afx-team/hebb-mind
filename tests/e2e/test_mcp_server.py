"""End-to-end test for the ``hebb-mcp`` stdio server: real subprocess + MCP handshake.

We spawn the server module directly (NOT the ``hebb-mcp`` console wrapper) because
``hebb.mcp.server.main`` calls ``_ensure_service_running()`` first, which would
auto-start the launchd/systemd daemon and bind it to a workspace db — a real
side effect we must never trigger from a test. The module's import-time
``capture_stdout()`` redirects stdout to stderr (stdio protection), so the
bypass restores it before ``mcp.run`` to keep the JSON-RPC stream on stdout.

This is the end-to-end regression test for the stdio guard: any stray write to
stdout corrupts the JSON-RPC framing and the handshake below fails.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(os.name != "posix", reason="stdio guard uses POSIX fd redirection"),
]

# MCP client SDK is a runtime dependency, but skip cleanly if unavailable.
pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

EXPECTED_TOOLS = {"write_memory", "search_memory", "consolidate", "ingest_conversation"}

# Run the server object directly, skipping the daemon-autostarting console wrapper.
_SERVER_BOOTSTRAP = (
    "from hebb.mcp.server import mcp, restore_stdout; "
    "restore_stdout(); "
    "mcp.run(transport='stdio')"
)


async def _list_tools() -> set[str]:
    params = StdioServerParameters(command=sys.executable, args=["-c", _SERVER_BOOTSTRAP])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return {tool.name for tool in result.tools}


async def test_mcp_initialize_and_list_tools() -> None:
    """Spawn hebb-mcp, complete the MCP handshake, and confirm the tools are exposed."""
    names = await asyncio.wait_for(_list_tools(), timeout=60)
    missing = EXPECTED_TOOLS - names
    assert not missing, f"MCP server is missing tools: {missing} (got {names})"
