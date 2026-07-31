"""Gemini CLI integration commands."""

from __future__ import annotations

import click


@click.group("gemini")
def gemini() -> None:
    """Gemini CLI integration — MCP server registration."""


@gemini.command("install")
def install() -> None:
    """Install Hebb Mind MCP into Gemini CLI settings.json."""
    from hebb.integrations.gemini_cli.install import handle

    handle()


@gemini.command("uninstall")
def uninstall() -> None:
    """Remove Hebb Mind MCP from Gemini CLI settings.json."""
    from hebb.integrations.gemini_cli.uninstall import handle

    handle()
