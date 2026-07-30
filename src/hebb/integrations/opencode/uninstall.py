"""Remove Hebb Mind MCP from opencode configuration."""

from __future__ import annotations

import click

from hebb.integrations._json_config import atomic_write, load_json
from hebb.integrations.opencode.install import SERVER_KEY, SERVER_NAME, config_path


def handle(scope: str = "user") -> None:
    """Remove Hebb Mind MCP from opencode.

    Args:
        scope: ``"project"`` or ``"user"``.
    """
    path = config_path(scope)
    data = load_json(path)
    servers = data.get(SERVER_KEY)
    if not isinstance(servers, dict) or SERVER_NAME not in servers:
        click.echo(f"Hebb Mind was not configured for opencode ({scope}).")
        return

    del servers[SERVER_NAME]
    atomic_write(path, _dump_json(data))

    click.secho(f"Removed Hebb Mind from opencode ({scope}).", fg="green")
    click.echo(f"  Config: {path}")
    click.echo("Start a new opencode session to apply the change.")


def _dump_json(data: dict) -> str:
    import json

    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
