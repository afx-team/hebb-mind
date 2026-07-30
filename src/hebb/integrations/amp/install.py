"""Install Hebb Mind MCP into Amp CLI settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from hebb.integrations._json_config import atomic_write, load_json
from hebb.utils.cli_paths import hebb_mcp_command, shell_quote

# Amp uses "amp.mcpServers" as the key (not "mcpServers")
SERVER_KEY = "amp.mcpServers"
SERVER_NAME = "hebb"


def config_path(scope: str) -> Path:
    """Resolve the Amp settings file path.

    Args:
        scope: ``"project"`` (``.amp/settings.json`` in cwd) or ``"user"``
            (``~/.config/amp/settings.json``).

    Returns:
        Path to the Amp settings file.
    """
    if scope == "project":
        return Path.cwd() / ".amp" / "settings.json"
    if scope == "user":
        return Path.home() / ".config" / "amp" / "settings.json"
    raise ValueError(f"Unsupported Amp scope: {scope}")


def build_entry(mcp_argv: list[str]) -> dict[str, Any]:
    """Build the Amp MCP server entry for Hebb."""
    entry: dict[str, Any] = {"command": mcp_argv[0]}
    if len(mcp_argv) > 1:
        entry["args"] = mcp_argv[1:]
    return entry


def handle(scope: str = "user") -> None:
    """Install Hebb Mind MCP into Amp CLI.

    Args:
        scope: ``"project"`` or ``"user"`` (default: ``"user"``).
    """
    mcp_argv = hebb_mcp_command()
    entry = build_entry(mcp_argv)
    path = config_path(scope)

    data = load_json(path)
    servers = data.get(SERVER_KEY)
    if not isinstance(servers, dict):
        servers = {}
        data[SERVER_KEY] = servers
    servers[SERVER_NAME] = entry

    import json

    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    click.secho(f"Installed Hebb Mind for Amp ({scope}).", fg="green")
    click.echo(f"  Config: {path}")
    click.echo(f"  Server command: {shell_quote(mcp_argv)}")
    if scope == "project":
        click.echo("  Settings merge with global Amp config when you run amp in this project.")
    click.echo("Start a new Amp session to activate the integration.")
