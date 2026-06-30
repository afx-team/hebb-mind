"""Remove Hebb Mind from Codex MCP and lifecycle configuration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import click

from hebb.integrations.codex.install import (
    atomic_write,
    config_path,
    hooks_path,
    remove_hebb_hooks,
    remove_project_mcp_table,
)


def uninstall_hooks(path: Path) -> bool:
    """Remove Hebb handlers from a Codex hooks file.

    Args:
        path: Target ``hooks.json`` path.

    Returns:
        Whether the file changed.

    Raises:
        click.ClickException: If the hooks file cannot be parsed.
    """
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(f"Cannot read Codex hooks file: {path}") from exc
    if not isinstance(data, dict):
        raise click.ClickException(f"Codex hooks file must contain an object: {path}")

    raw_hooks = data.get("hooks")
    if not isinstance(raw_hooks, dict):
        return False
    before = json.dumps(raw_hooks, sort_keys=True)
    hooks: dict[str, Any] = raw_hooks
    remove_hebb_hooks(hooks)
    if json.dumps(hooks, sort_keys=True) == before:
        return False
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return True


def uninstall_project_mcp(path: Path) -> bool:
    """Remove project-scoped Hebb MCP configuration.

    Args:
        path: Project ``config.toml`` path.

    Returns:
        Whether the file changed.
    """
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8")
    updated = remove_project_mcp_table(original)
    if updated == original:
        return False
    atomic_write(path, updated.rstrip() + ("\n" if updated.strip() else ""))
    return True


def handle(scope: str) -> None:
    """Remove Hebb MCP and hooks for a Codex scope.

    Args:
        scope: ``project`` or ``user``.

    Raises:
        click.ClickException: If Codex rejects user-level MCP removal.
    """
    changed = uninstall_hooks(hooks_path(scope))
    if scope == "user":
        result = subprocess.run(
            ["codex", "mcp", "remove", "hebb"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 and "not found" not in result.stderr.lower():
            detail = result.stderr.strip() or "codex mcp remove failed"
            raise click.ClickException(detail)
        changed = result.returncode == 0 or changed
    else:
        changed = uninstall_project_mcp(config_path(scope)) or changed

    if changed:
        click.secho(f"Removed Hebb Mind from Codex ({scope}).", fg="green")
    else:
        click.echo(f"Hebb Mind was not configured for Codex ({scope}).")
    if scope == "project":
        click.echo("Scope was project only; user-wide Codex config was not changed.")
    else:
        click.echo("Scope was current user; project-local .codex/ files were not changed.")
    click.echo("Start a new Codex thread to apply the change.")
