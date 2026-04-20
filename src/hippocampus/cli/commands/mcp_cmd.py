"""hippocampus mcp — start MCP server in stdio mode."""

from __future__ import annotations

import click


@click.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server (stdio transport).

    Requires the hippocampus service to be running (`hippocampus start`).
    This provides write_memory, search_memory, and consolidate tools
    for Claude Code, Cursor, and other MCP-compatible clients.
    """
    from hippocampus.mcp.server import main

    main()
