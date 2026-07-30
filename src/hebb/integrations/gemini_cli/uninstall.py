"""Remove Hebb Mind MCP from Gemini CLI settings."""

from __future__ import annotations

import click

from hebb.integrations._json_config import remove_server
from hebb.integrations.gemini_cli.install import SERVER_KEY, SERVER_NAME, config_path


def handle() -> None:
    """Remove Hebb Mind MCP from Gemini CLI."""
    path = config_path()
    changed = remove_server(path, SERVER_KEY, SERVER_NAME)

    if changed:
        click.secho("Removed Hebb Mind from Gemini CLI.", fg="green")
    else:
        click.echo("Hebb Mind was not configured for Gemini CLI.")
    click.echo(f"  Config: {path}")
    click.echo("Start a new Gemini CLI session to apply the change.")
