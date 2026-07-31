"""Install Hebb Mind MCP into opencode configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from hebb.integrations._json_config import upsert_server
from hebb.utils.cli_paths import hebb_mcp_command, shell_quote

SERVER_KEY = "mcp"
SERVER_NAME = "hebb"


def config_path(scope: str) -> Path:
    """Resolve the opencode configuration path for an installation scope.

    Args:
        scope: ``"project"`` (``opencode.json`` in cwd) or ``"user"``
            (``~/.config/opencode/opencode.json``).

    Returns:
        Path to the opencode config file.
    """
    if scope == "project":
        return Path.cwd() / "opencode.json"
    if scope == "user":
        return Path.home() / ".config" / "opencode" / "opencode.json"
    raise ValueError(f"Unsupported opencode scope: {scope}")


def build_entry(mcp_argv: list[str]) -> dict[str, Any]:
    """Build the opencode MCP server entry for Hebb.

    opencode uses ``command`` as a flat array (command + args combined),
    not separate ``command`` + ``args`` fields like most other clients.
    """
    return {
        "type": "local",
        "command": mcp_argv,
        "enabled": True,
    }


def handle(scope: str = "user") -> None:
    """Install Hebb Mind MCP into opencode.

    Args:
        scope: ``"project"`` or ``"user"`` (default: ``"user"``).

    Raises:
        click.ClickException: If the config file exists but cannot be parsed.
    """
    mcp_argv = hebb_mcp_command()
    entry = build_entry(mcp_argv)
    path = config_path(scope)

    upsert_server(path, SERVER_KEY, SERVER_NAME, entry)

    click.secho(f"Installed Hebb Mind for opencode ({scope}).", fg="green")
    click.echo(f"  Config: {path}")
    click.echo(f"  Server command: {shell_quote(mcp_argv)}")
    click.echo("Verify with: opencode mcp list")
    click.echo("Start a new opencode session to activate the integration.")
