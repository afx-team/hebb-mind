"""Codex CLI integration commands."""

from __future__ import annotations

import shutil
import subprocess

import click


@click.group("codex")
def codex() -> None:
    """Codex integration — configure Hebb Mind as an MCP server."""


@codex.command("install")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user", show_default=True)
def install(scope: str) -> None:
    """Install Hebb Mind MCP into Codex."""
    _ensure_codex()
    if scope == "project":
        click.secho("Codex CLI currently stores MCP servers in its config; using codex mcp add.", fg="yellow")

    result = subprocess.run(["codex", "mcp", "add", "hebb", "--", "hebb-mcp"], check=False)
    if result.returncode != 0:
        raise click.ClickException("codex mcp add failed")

    click.secho("Installed hebb MCP server for Codex.", fg="green")
    click.echo("Verify with: codex mcp list")


@codex.command("uninstall")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user", show_default=True)
def uninstall(scope: str) -> None:
    """Remove Hebb Mind MCP from Codex."""
    _ensure_codex()
    if scope == "project":
        click.secho("Codex CLI currently removes MCP servers from its config; using codex mcp remove.", fg="yellow")

    result = subprocess.run(["codex", "mcp", "remove", "hebb"], check=False)
    if result.returncode != 0:
        raise click.ClickException("codex mcp remove failed")

    click.secho("Removed hebb MCP server from Codex.", fg="green")


def _ensure_codex() -> None:
    if not shutil.which("codex"):
        raise click.ClickException("codex CLI not found on PATH")
