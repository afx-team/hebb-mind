"""hebb claude-code install — configure Claude Code hooks and MCP server.

All commands we write into ``settings.json`` and ``claude mcp add`` are
**absolute paths** resolved via :mod:`hebb.utils.cli_paths`. Bare names
like ``hebb`` / ``hebb-mcp`` are not safe to inject — Claude Code
launches hooks and MCP servers as subprocesses whose PATH comes from
launchd (macOS) or the GUI process tree, *not* from the user's shell
rc, and ``pip install --user`` lands scripts in a directory that's
typically not on that PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import click

from hebb.utils.cli_paths import hebb_command, hebb_mcp_command, shell_quote


def _hooks_config() -> dict[str, list[dict[str, object]]]:
    """Build the hook block with absolute commands resolved at install time."""
    hebb = hebb_command()
    return {
        "SessionStart": [
            {
                "matcher": "",
                "hooks": [
                    {"type": "command", "command": shell_quote([*hebb, "claude-code", "recall"]), "timeout": 30},
                ],
            }
        ],
        "UserPromptSubmit": [
            {
                "matcher": "",
                "hooks": [
                    {"type": "command", "command": shell_quote([*hebb, "claude-code", "write"]), "timeout": 10},
                ],
            }
        ],
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {"type": "command", "command": shell_quote([*hebb, "claude-code", "stop"]), "timeout": 30},
                ],
            }
        ],
    }


def _mcp_server_config() -> dict[str, dict[str, object]]:
    mcp = hebb_mcp_command()
    return {
        "hebb": {
            "type": "stdio",
            "command": mcp[0],
            "args": mcp[1:] if len(mcp) > 1 else [],
        }
    }


def _find_settings_path(scope: str) -> Path:
    """Resolve the target settings.json path."""
    if scope == "project":
        return Path.cwd() / ".claude" / "settings.json"
    return Path.home() / ".claude" / "settings.json"


def _load_settings(path: Path) -> dict[str, object]:
    """Load existing settings or return empty dict."""
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_settings(path: Path, settings: dict[str, object]) -> None:
    """Write settings to file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


def _is_hebb_hook(command: str) -> bool:
    """Match every shape of hebb-installed hook command we may have written.

    Covers both the current ``claude-code`` name and the legacy ``cc`` name
    in three shapes: bare entry-point, absolute path, and ``python -m``
    fallback.
    """
    return any(
        marker in command
        for marker in (
            "hebb claude-code ",
            "/hebb claude-code ",
            "hebb.cli.main claude-code ",
            "hebb cc ",
            "/hebb cc ",
            "hebb.cli.main cc ",
        )
    )


def handle(scope: str) -> None:
    """Install hebb hooks and MCP server into Claude Code settings."""
    hebb_argv = hebb_command()
    mcp_argv = hebb_mcp_command()

    # Sanity: warn if neither real binary nor `python -m` fallback is usable.
    if hebb_argv[0].endswith(("python", "python3", "python3.10", "python3.11", "python3.12", "python3.13")):
        click.secho(
            "Note: `hebb` not on PATH; using `python -m hebb.cli.main` instead.",
            fg="yellow",
        )

    # Load settings
    settings_path = _find_settings_path(scope)
    settings = _load_settings(settings_path)

    # Inject hooks — replace any existing hebb hook (bare or absolute) with the
    # freshly-resolved absolute one. Idempotent: re-running picks up a new
    # install location automatically.
    hooks_config = _hooks_config()
    raw_hooks = settings.get("hooks", {})
    existing_hooks: dict[str, list[dict[str, object]]] = raw_hooks if isinstance(raw_hooks, dict) else {}
    for event, hook_list in hooks_config.items():
        existing = existing_hooks.get(event, [])
        # Drop any prior hebb entries before adding the new one.
        cleaned: list[dict[str, object]] = []
        for entry in existing:
            inner_raw = entry.get("hooks", [])
            if not isinstance(inner_raw, list):
                continue
            inner = [h for h in inner_raw if isinstance(h, dict) and not _is_hebb_hook(str(h.get("command", "")))]
            if inner:
                cleaned.append({**entry, "hooks": inner})
        existing_hooks[event] = cleaned + hook_list
    settings["hooks"] = existing_hooks

    # Install MCP server. Prefer the official Claude CLI so `claude mcp list`
    # matches user expectations, then fall back to settings.json.
    mcp_installed_with_cli = _install_mcp_with_claude_cli(scope, mcp_argv)
    if not mcp_installed_with_cli:
        raw_mcp = settings.get("mcpServers", {})
        mcp_servers: dict[str, object] = raw_mcp if isinstance(raw_mcp, dict) else {}
        mcp_servers["hebb"] = _mcp_server_config()["hebb"]
        settings["mcpServers"] = mcp_servers

    _save_settings(settings_path, settings)

    click.secho(f"Installed hebb into {settings_path}", fg="green")
    click.echo("  Hooks:  SessionStart (recall), UserPromptSubmit (write), Stop (consolidate)")
    click.echo(f"  hebb:   {shell_quote(hebb_argv)}")
    click.echo(
        f"  MCP:    {shell_quote(mcp_argv)}"
        + ("  (via claude mcp add)" if mcp_installed_with_cli else "  (via settings.json)")
    )
    click.echo("")
    click.echo("Verify MCP with: claude mcp list")
    click.echo("Restart Claude Code to activate hooks.")


def _install_mcp_with_claude_cli(scope: str, mcp_argv: list[str]) -> bool:
    """Register the MCP server through ``claude mcp add`` (preferred)."""
    if not shutil.which("claude"):
        return False
    # Re-add: replace any prior hebb entry so the absolute path is current.
    subprocess.run(["claude", "mcp", "remove", "hebb", "-s", scope], capture_output=True, check=False)
    cmd = [
        "claude",
        "mcp",
        "add",
        "--transport",
        "stdio",
        "--scope",
        scope,
        "hebb",
        "--",
        *mcp_argv,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0
