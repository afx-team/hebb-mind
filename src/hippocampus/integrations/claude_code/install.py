"""hippocampus cc install — configure Claude Code hooks and MCP server."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

# The hooks and MCP config to inject
_HOOKS_CONFIG = {
    "SessionStart": [
        {"matcher": "", "hooks": [{"type": "command", "command": "hippocampus cc recall", "timeout": 30}]}
    ],
    "UserPromptSubmit": [
        {"matcher": "", "hooks": [{"type": "command", "command": "hippocampus cc write", "timeout": 10}]}
    ],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "hippocampus cc stop", "timeout": 30}]}],
}

_MCP_SERVER_CONFIG = {
    "hippocampus": {
        "type": "stdio",
        "command": "hippocampus-mcp",
    }
}


def _find_settings_path(scope: str) -> Path:
    """Resolve the target settings.json path."""
    if scope == "project":
        # Walk up from cwd to find .claude/ or create in cwd
        cwd = Path.cwd()
        candidate = cwd / ".claude" / "settings.json"
        return candidate
    else:
        return Path.home() / ".claude" / "settings.json"


def _load_settings(path: Path) -> dict:
    """Load existing settings or return empty dict."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_settings(path: Path, settings: dict) -> None:
    """Write settings to file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


def handle(scope: str) -> None:
    """Install hippocampus hooks and MCP server into Claude Code settings."""
    # 1. Verify hippocampus-mcp is available
    if not shutil.which("hippocampus-mcp"):
        click.secho("Warning: hippocampus-mcp not found on PATH.", fg="yellow")
        click.echo("  Run: pip install afx-hippocampus  (or pip install -e .)")

    if not shutil.which("hippocampus"):
        click.secho("Error: hippocampus CLI not found on PATH.", fg="red")
        raise SystemExit(1)

    # 2. Load settings
    settings_path = _find_settings_path(scope)
    settings = _load_settings(settings_path)

    # 3. Inject hooks
    existing_hooks = settings.get("hooks", {})
    for event, hook_list in _HOOKS_CONFIG.items():
        if event not in existing_hooks:
            existing_hooks[event] = hook_list
        else:
            # Check if our hook is already present
            existing_commands = {
                h.get("command", "") for entry in existing_hooks[event] for h in entry.get("hooks", [])
            }
            if "hippocampus cc" not in " ".join(existing_commands):
                existing_hooks[event].extend(hook_list)
    settings["hooks"] = existing_hooks

    # 4. Inject MCP server
    mcp_servers = settings.get("mcpServers", {})
    if "hippocampus" not in mcp_servers:
        mcp_servers["hippocampus"] = _MCP_SERVER_CONFIG["hippocampus"]
    settings["mcpServers"] = mcp_servers

    # 5. Save
    _save_settings(settings_path, settings)

    click.secho(f"Installed hippocampus into {settings_path}", fg="green")
    click.echo("  Hooks:  SessionStart (recall), UserPromptSubmit (write), Stop (consolidate)")
    click.echo("  MCP:    hippocampus (write_memory, search_memory, consolidate)")
    click.echo("")
    click.echo("Restart Claude Code to activate.")
