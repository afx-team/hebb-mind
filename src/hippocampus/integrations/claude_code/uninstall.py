"""hippocampus cc uninstall — remove hooks and MCP server from Claude Code."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import click


def _find_settings_path(scope: str) -> Path:
    if scope == "project":
        return Path.cwd() / ".claude" / "settings.json"
    else:
        return Path.home() / ".claude" / "settings.json"


def handle(scope: str) -> None:
    """Remove hippocampus hooks and MCP server from Claude Code settings."""
    _remove_mcp_with_claude_cli(scope)
    settings_path = _find_settings_path(scope)

    if not settings_path.exists():
        click.echo(f"No settings found at {settings_path}")
        return

    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        click.secho(f"Error reading {settings_path}", fg="red")
        return

    changed = False

    # Remove hooks containing "hippocampus cc"
    hooks = settings.get("hooks", {})
    for event in list(hooks.keys()):
        filtered = []
        for entry in hooks[event]:
            entry_hooks = entry.get("hooks", [])
            kept = [h for h in entry_hooks if "hippocampus cc" not in h.get("command", "")]
            if kept:
                entry["hooks"] = kept
                filtered.append(entry)
        if filtered:
            hooks[event] = filtered
        else:
            del hooks[event]
            changed = True

    if hooks != settings.get("hooks", {}):
        settings["hooks"] = hooks
        changed = True
    if not hooks and "hooks" in settings:
        del settings["hooks"]
        changed = True

    # Remove MCP server
    mcp_servers = settings.get("mcpServers", {})
    if "hippocampus" in mcp_servers:
        del mcp_servers["hippocampus"]
        changed = True
    if mcp_servers:
        settings["mcpServers"] = mcp_servers
    elif "mcpServers" in settings:
        del settings["mcpServers"]

    if changed:
        settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        click.secho(f"Removed hippocampus from {settings_path}", fg="green")
    else:
        click.echo("hippocampus not found in settings, nothing to remove.")

    click.echo("Restart Claude Code to apply.")


def _remove_mcp_with_claude_cli(scope: str) -> None:
    if not shutil.which("claude"):
        return
    subprocess.run(
        ["claude", "mcp", "remove", "--scope", scope, "hippocampus"],
        capture_output=True,
        text=True,
        check=False,
    )
