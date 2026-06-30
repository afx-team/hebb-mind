"""Install Hebb Mind into Codex MCP and lifecycle configuration."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import click

from hebb.utils.cli_paths import hebb_command, hebb_mcp_command, shell_quote


def config_path(scope: str) -> Path:
    """Resolve the Codex configuration path for an installation scope.

    Args:
        scope: Either ``project`` or ``user``.

    Returns:
        Path to the active ``config.toml`` layer.

    Raises:
        ValueError: If the scope is unsupported.
    """
    if scope == "project":
        return Path.cwd() / ".codex" / "config.toml"
    if scope == "user":
        return Path.home() / ".codex" / "config.toml"
    raise ValueError(f"Unsupported Codex scope: {scope}")


def hooks_path(scope: str) -> Path:
    """Resolve the Codex hooks path for an installation scope.

    Args:
        scope: Either ``project`` or ``user``.

    Returns:
        Path to the active ``hooks.json`` layer.
    """
    return config_path(scope).with_name("hooks.json")


def hooks_config() -> dict[str, list[dict[str, object]]]:
    """Build Codex lifecycle hooks with an absolute Hebb command."""
    hebb = hebb_command()
    return {
        "SessionStart": [
            {
                "matcher": "startup|resume|clear|compact",
                "hooks": [
                    {
                        "type": "command",
                        "command": shell_quote([*hebb, "codex", "recall"]),
                        "timeout": 30,
                        "statusMessage": "Recalling Hebb Mind context",
                    }
                ],
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": shell_quote([*hebb, "codex", "prompt"]),
                        "timeout": 10,
                        "statusMessage": "Searching Hebb Mind",
                    }
                ],
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": shell_quote([*hebb, "codex", "stop"]),
                        "timeout": 30,
                        "statusMessage": "Saving turn to Hebb Mind",
                    }
                ],
            }
        ],
    }


def is_hebb_hook(command: str) -> bool:
    """Return whether a hook command belongs to Hebb Mind.

    Args:
        command: Hook command string.

    Returns:
        ``True`` for current Codex commands and legacy Claude-routed commands.
    """
    return any(
        marker in command
        for marker in (
            "hebb codex ",
            "/hebb codex ",
            "hebb.cli.main codex ",
            "hebb claude-code ",
            "/hebb claude-code ",
            "hebb.cli.main claude-code ",
        )
    )


def install_hooks(path: Path) -> None:
    """Merge Hebb lifecycle hooks into a Codex hooks file.

    Args:
        path: Target ``hooks.json`` path.

    Raises:
        click.ClickException: If an existing hooks file is invalid.
    """
    data: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise click.ClickException(f"Cannot read Codex hooks file: {path}") from exc
        if not isinstance(loaded, dict):
            raise click.ClickException(f"Codex hooks file must contain an object: {path}")
        data = loaded

    raw_hooks = data.get("hooks", {})
    hooks: dict[str, Any] = raw_hooks if isinstance(raw_hooks, dict) else {}
    remove_hebb_hooks(hooks)
    for event, entries in hooks_config().items():
        existing = hooks.get(event, [])
        if not isinstance(existing, list):
            existing = []
        hooks[event] = [*existing, *entries]
    data["hooks"] = hooks
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def install_project_mcp(path: Path, mcp_argv: list[str]) -> None:
    """Upsert the project-scoped Hebb MCP table in Codex TOML.

    Args:
        path: Project ``.codex/config.toml`` path.
        mcp_argv: Absolute command and arguments for the MCP server.
    """
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = remove_project_mcp_table(existing).rstrip()
    block = _mcp_toml(mcp_argv)
    output = f"{cleaned}\n\n{block}" if cleaned else block
    atomic_write(path, output)


def remove_project_mcp_table(text: str) -> str:
    """Remove Hebb's MCP TOML table while preserving unrelated config.

    Args:
        text: Existing Codex TOML source.

    Returns:
        TOML source without ``mcp_servers.hebb`` tables.
    """
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            table = stripped.strip("[]").strip()
            skipping = table == "mcp_servers.hebb" or table.startswith("mcp_servers.hebb.")
        if not skipping:
            output.append(line)
    return "".join(output)


def handle(scope: str) -> None:
    """Install Hebb MCP and hooks for Codex.

    Args:
        scope: ``project`` or ``user``.

    Raises:
        click.ClickException: If Codex rejects user-level MCP registration.
    """
    mcp_argv = hebb_mcp_command()
    target_hooks = hooks_path(scope)

    if scope == "user":
        subprocess.run(["codex", "mcp", "remove", "hebb"], capture_output=True, check=False)
        result = subprocess.run(
            ["codex", "mcp", "add", "hebb", "--", *mcp_argv],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or "codex mcp add failed"
            raise click.ClickException(detail)
    else:
        install_project_mcp(config_path(scope), mcp_argv)

    install_hooks(target_hooks)

    click.secho(f"Installed Hebb Mind for Codex ({scope}).", fg="green")
    if scope == "project":
        click.echo("  Scope: project only; applies to this repository after Codex trusts it.")
        click.echo(f"  MCP:   {config_path(scope)}")
    else:
        click.echo("  Scope: current user; applies to all Codex projects for this OS user.")
        click.echo("  MCP:   registered with `codex mcp add hebb`")
    click.echo(f"  Hooks: {target_hooks}")
    click.echo(f"  Server command: {shell_quote(mcp_argv)}")
    click.echo("Verify MCP with: codex mcp list")
    click.echo("Review and trust lifecycle hooks with: /hooks")
    if scope == "project":
        click.echo("Codex must trust this project before project configuration and hooks load.")
    click.echo("Start a new Codex thread to activate the integration.")


def remove_hebb_hooks(hooks: dict[str, Any]) -> None:
    """Remove Hebb-managed handlers from every hook event in place.

    Args:
        hooks: Mutable Codex hook event mapping.
    """
    for event in list(hooks):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        kept_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            handlers = entry.get("hooks")
            if not isinstance(handlers, list):
                continue
            kept_handlers = [
                handler
                for handler in handlers
                if isinstance(handler, dict) and not is_hebb_hook(str(handler.get("command", "")))
            ]
            if kept_handlers:
                kept_entries.append({**entry, "hooks": kept_handlers})
        if kept_entries:
            hooks[event] = kept_entries
        else:
            hooks.pop(event, None)


def atomic_write(path: Path, content: str) -> None:
    """Atomically replace a UTF-8 text file, creating its parent.

    Args:
        path: Destination file.
        content: Complete replacement content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _mcp_toml(mcp_argv: list[str]) -> str:
    """Render the Hebb MCP table as valid TOML."""
    command = json.dumps(mcp_argv[0], ensure_ascii=True)
    args = json.dumps(mcp_argv[1:], ensure_ascii=True)
    return f"[mcp_servers.hebb]\ncommand = {command}\nargs = {args}\n"
