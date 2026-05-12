"""Codex CLI integration commands."""

from __future__ import annotations

import shutil
import subprocess

import click


@click.group("codex")
def codex() -> None:
    """Codex integration — configure Hippocampus as an MCP server."""


@codex.command("install")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user", show_default=True)
def install(scope: str) -> None:
    """Install Hippocampus MCP into Codex."""
    _ensure_codex()
    if scope == "project":
        click.secho("Codex CLI currently stores MCP servers in its config; using codex mcp add.", fg="yellow")

    result = subprocess.run(["codex", "mcp", "add", "hippocampus", "--", "hippocampus-mcp"], check=False)
    if result.returncode != 0:
        raise click.ClickException("codex mcp add failed")

    click.secho("Installed hippocampus MCP server for Codex.", fg="green")
    click.echo("Verify with: codex mcp list")


@codex.command("uninstall")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user", show_default=True)
def uninstall(scope: str) -> None:
    """Remove Hippocampus MCP from Codex."""
    _ensure_codex()
    if scope == "project":
        click.secho("Codex CLI currently removes MCP servers from its config; using codex mcp remove.", fg="yellow")

    result = subprocess.run(["codex", "mcp", "remove", "hippocampus"], check=False)
    if result.returncode != 0:
        raise click.ClickException("codex mcp remove failed")

    click.secho("Removed hippocampus MCP server from Codex.", fg="green")


def _ensure_codex() -> None:
    if not shutil.which("codex"):
        raise click.ClickException("codex CLI not found on PATH")
