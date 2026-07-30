"""Remove Hebb Mind MCP from opencode configuration."""

from __future__ import annotations

import click

from hebb.integrations._json_config import remove_server
from hebb.integrations.opencode.install import SERVER_KEY, SERVER_NAME, config_path


def handle(scope: str = "user") -> None:
    """Remove Hebb Mind MCP from opencode.

    Args:
        scope: ``"project"`` or ``"user"``.

    Raises:
        click.ClickException: If the config file exists but cannot be parsed.
    """
    path = config_path(scope)
    changed = remove_server(path, SERVER_KEY, SERVER_NAME)

    if changed:
        click.secho(f"Removed Hebb Mind from opencode ({scope}).", fg="green")
    else:
        click.echo(f"Hebb Mind was not configured for opencode ({scope}).")
    click.echo(f"  Config: {path}")
    click.echo("Start a new opencode session to apply the change.")
