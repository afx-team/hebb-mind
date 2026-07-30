"""Remove Hebb Mind MCP from Amp CLI settings."""

from __future__ import annotations

import click

from hebb.integrations._json_config import atomic_write, load_json
from hebb.integrations.amp.install import SERVER_KEY, SERVER_NAME, config_path


def handle(scope: str = "user") -> None:
    """Remove Hebb Mind MCP from Amp CLI.

    Args:
        scope: ``"project"`` or ``"user"``.
    """
    path = config_path(scope)
    data = load_json(path)
    servers = data.get(SERVER_KEY)
    if not isinstance(servers, dict) or SERVER_NAME not in servers:
        click.echo(f"Hebb Mind was not configured for Amp ({scope}).")
        return

    del servers[SERVER_NAME]

    import json

    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    click.secho(f"Removed Hebb Mind from Amp ({scope}).", fg="green")
    click.echo(f"  Config: {path}")
    click.echo("Start a new Amp session to apply the change.")
