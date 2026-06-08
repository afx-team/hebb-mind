"""Codex CLI integration commands."""

from __future__ import annotations

import shutil
import subprocess

import click

from hebb.utils.cli_paths import hebb_mcp_command, shell_quote


@click.group("codex")
def codex() -> None:
    """Codex integration — configure Hebb Mind as an MCP server."""


@codex.command("install")
@click.option(
    "--scope",
    type=click.Choice(["user"]),
    default="user",
    show_default=True,
    help="Codex stores MCP servers globally in its config; only 'user' (global) is supported.",
)
def install(scope: str) -> None:
    """Install Hebb Mind MCP into Codex.

    Codex registers MCP servers globally via ``codex mcp add`` — there is no
    per-project scope, so this command is global-only.
    """
    _ensure_codex()

    # Resolve absolute path to hebb-mcp — Codex launches the MCP server as a
    # subprocess whose PATH may not include `pip install --user` bin dirs.
    mcp_argv = hebb_mcp_command()
    # Replace any prior entry so a fresh install picks up a moved binary.
    subprocess.run(["codex", "mcp", "remove", "hebb"], capture_output=True, check=False)
    result = subprocess.run(["codex", "mcp", "add", "hebb", "--", *mcp_argv], check=False)
    if result.returncode != 0:
        raise click.ClickException("codex mcp add failed")

    click.secho("Installed hebb MCP server for Codex.", fg="green")
    click.echo(f"  MCP: {shell_quote(mcp_argv)}")
    click.echo("Verify with: codex mcp list")


@codex.command("uninstall")
@click.option(
    "--scope",
    type=click.Choice(["user"]),
    default="user",
    show_default=True,
    help="Codex stores MCP servers globally in its config; only 'user' (global) is supported.",
)
def uninstall(scope: str) -> None:
    """Remove Hebb Mind MCP from Codex (global-only)."""
    _ensure_codex()

    result = subprocess.run(["codex", "mcp", "remove", "hebb"], check=False)
    if result.returncode != 0:
        raise click.ClickException("codex mcp remove failed")

    click.secho("Removed hebb MCP server from Codex.", fg="green")


def _ensure_codex() -> None:
    if not shutil.which("codex"):
        raise click.ClickException("codex CLI not found on PATH")
