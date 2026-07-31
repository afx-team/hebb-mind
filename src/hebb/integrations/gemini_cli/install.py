"""Install Hebb Mind MCP into Gemini CLI settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from hebb.integrations._json_config import upsert_server
from hebb.utils.cli_paths import hebb_mcp_command, shell_quote

SERVER_KEY = "mcpServers"
SERVER_NAME = "hebb"


def config_path() -> Path:
    """Resolve the Gemini CLI settings file path."""
    return Path.home() / ".gemini" / "settings.json"


def build_entry(mcp_argv: list[str]) -> dict[str, Any]:
    """Build the Gemini CLI MCP server entry for Hebb."""
    entry: dict[str, Any] = {"command": mcp_argv[0]}
    if len(mcp_argv) > 1:
        entry["args"] = mcp_argv[1:]
    return entry


def handle() -> None:
    """Install Hebb Mind MCP into Gemini CLI.

    Raises:
        click.ClickException: If the config file exists but cannot be parsed.
    """
    mcp_argv = hebb_mcp_command()
    entry = build_entry(mcp_argv)
    path = config_path()

    written = upsert_server(path, SERVER_KEY, SERVER_NAME, entry)

    click.secho("Installed Hebb Mind for Gemini CLI.", fg="green")
    click.echo(f"  Config: {path}")
    click.echo(f"  Server command: {shell_quote(mcp_argv)}")
    if not written:
        click.echo("  (already configured — entry refreshed)")
    click.echo("Verify with: gemini /mcp")
    click.echo("Start a new Gemini CLI session to activate the integration.")
