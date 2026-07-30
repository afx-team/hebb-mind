"""Remove Hebb Mind MCP from Goose config.yaml."""

from __future__ import annotations

import click

from hebb.integrations.goose.install import _remove_hebb_block, atomic_write, config_path


def handle() -> None:
    """Remove Hebb Mind MCP from Goose."""
    path = config_path()
    if not path.exists():
        click.echo("Hebb Mind was not configured for Goose.")
        return

    existing = path.read_text(encoding="utf-8")
    cleaned = _remove_hebb_block(existing)

    if cleaned == existing:
        click.echo("Hebb Mind was not configured for Goose.")
        return

    atomic_write(path, cleaned)
    click.secho("Removed Hebb Mind from Goose.", fg="green")
    click.echo(f"  Config: {path}")
    click.echo("Start a new Goose session to apply the change.")
