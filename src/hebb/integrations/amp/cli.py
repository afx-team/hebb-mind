"""Amp CLI integration commands."""

from __future__ import annotations

import click


@click.group("amp")
def amp() -> None:
    """Amp CLI integration — MCP server registration."""


@amp.command("install")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="user",
    show_default=True,
    help="Where to install: 'project' writes .amp/settings.json; 'user' writes global config.",
)
def install(scope: str) -> None:
    """Install Hebb Mind MCP into Amp CLI."""
    from hebb.integrations.amp.install import handle

    handle(scope)


@amp.command("uninstall")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="user",
    show_default=True,
    help="Where to remove from.",
)
def uninstall(scope: str) -> None:
    """Remove Hebb Mind MCP from Amp CLI."""
    from hebb.integrations.amp.uninstall import handle

    handle(scope)
