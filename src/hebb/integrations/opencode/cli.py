"""opencode integration commands."""

from __future__ import annotations

import click


@click.group("opencode")
def opencode() -> None:
    """opencode integration — MCP server registration."""


@opencode.command("install")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="user",
    show_default=True,
    help="Where to install: 'project' writes opencode.json in cwd; 'user' writes the global config.",
)
def install(scope: str) -> None:
    """Install Hebb Mind MCP into opencode."""
    from hebb.integrations.opencode.install import handle

    handle(scope)


@opencode.command("uninstall")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="user",
    show_default=True,
    help="Where to remove from.",
)
def uninstall(scope: str) -> None:
    """Remove Hebb Mind MCP from opencode."""
    from hebb.integrations.opencode.uninstall import handle

    handle(scope)
