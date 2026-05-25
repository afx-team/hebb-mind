"""hebb mcp — MCP server commands."""

from __future__ import annotations

import click


@click.group("mcp")
def mcp_cmd() -> None:
    """MCP server commands (Model Context Protocol)."""


@mcp_cmd.command("serve")
def mcp_serve() -> None:
    """Start the MCP stdio server (for editor integrations).

    Requires the hebb background service to be installed
    (``hebb service install``). The MCP server will ask the OS service
    manager to start it if it isn't already running. This provides
    write_memory, search_memory, and consolidate tools for Claude Code,
    Cursor, and other MCP-compatible clients.
    """
    from hebb.mcp.server import main

    main()
