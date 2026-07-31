"""Goose integration commands."""

from __future__ import annotations

import click


@click.group("goose")
def goose() -> None:
    """Goose integration — MCP server registration."""


@goose.command("install")
def install() -> None:
    """Install Hebb Mind MCP into Goose config.yaml."""
    from hebb.integrations.goose.install import handle

    handle()


@goose.command("uninstall")
def uninstall() -> None:
    """Remove Hebb Mind MCP from Goose config.yaml."""
    from hebb.integrations.goose.uninstall import handle

    handle()
