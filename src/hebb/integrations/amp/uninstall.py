"""Remove Hebb Mind MCP from Amp CLI settings."""

from __future__ import annotations

import click

from hebb.integrations._json_config import remove_server
from hebb.integrations.amp.install import SERVER_KEY, SERVER_NAME, config_path


def handle(scope: str = "user") -> None:
    """Remove Hebb Mind MCP from Amp CLI.

    Args:
        scope: ``"project"`` or ``"user"``.
    """
    path = config_path(scope)
    changed = remove_server(path, SERVER_KEY, SERVER_NAME)

    if changed:
        click.secho(f"Removed Hebb Mind from Amp ({scope}).", fg="green")
    else:
        click.echo(f"Hebb Mind was not configured for Amp ({scope}).")
    click.echo(f"  Config: {path}")
    click.echo("Start a new Amp session to apply the change.")
