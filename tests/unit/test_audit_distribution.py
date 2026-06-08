"""Distribution-surface audit tests (Lane A-distribution).

Guards against the distribution-breakage class of defects where shipped
integration manifests (Claude Code plugin, Codex hooks) or the Docker image
reference CLI commands that do not exist in the registered Click command tree.
A typo or a renamed subcommand silently breaks every install, so these tests
resolve each shipped command string back to a real Click command.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import click

from hebb.cli.main import main

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
CODEX_HOOKS_JSON = REPO_ROOT / ".codex" / "hooks.json"
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"


def _resolve_command(tokens: list[str]) -> bool:
    """Resolve a token path (e.g. ``["claude-code", "recall"]``) to a command.

    Walks the Click group tree token by token. Once a leaf (non-group) command
    is reached, any remaining tokens are treated as positional arguments to that
    command (e.g. ``config set <key> <value>``) and resolution succeeds.

    Args:
        tokens: The command path with the leading ``hebb`` executable removed.

    Returns:
        True if the leading tokens resolve to a registered Click command.
    """
    cmd: click.Command = main
    ctx = click.Context(main)
    for token in tokens:
        if not isinstance(cmd, click.Group):
            # Reached a leaf command; remaining tokens are its arguments.
            return True
        sub = cmd.get_command(ctx, token)
        if sub is None:
            return False
        cmd = sub
    return True


def _extract_hook_commands(manifest: Path) -> list[str]:
    """Collect every ``command`` string from a hook manifest's hook entries.

    Args:
        manifest: Path to a JSON file with a ``hooks`` section.

    Returns:
        The list of command strings found under every hook entry.
    """
    data = json.loads(manifest.read_text())
    commands: list[str] = []
    for event_groups in data["hooks"].values():
        for group in event_groups:
            for hook in group["hooks"]:
                if hook.get("type") == "command":
                    commands.append(hook["command"])
    return commands


def _hebb_invocations(command: str) -> list[list[str]]:
    """Return the ``hebb`` sub-command token paths embedded in a shell command.

    Args:
        command: A shell command string that may contain one or more ``hebb``
            invocations (e.g. a Dockerfile ``CMD`` chain).

    Returns:
        A list of token paths (each with the leading ``hebb`` stripped), one per
        ``hebb`` invocation found.
    """
    invocations: list[list[str]] = []
    for match in re.finditer(r"\bhebb\b([^;&|]*)", command):
        tail = match.group(1).strip()
        if not tail:
            invocations.append([])
            continue
        tokens: list[str] = []
        for tok in tail.split():
            if tok.startswith("-"):
                break  # first option ends the sub-command path
            tokens.append(tok)
        invocations.append(tokens)
    return invocations


def test_plugin_hook_commands_resolve() -> None:
    """Every command in the Claude Code plugin manifest is a real CLI command."""
    commands = _extract_hook_commands(PLUGIN_JSON)
    assert commands, "plugin.json declared no hook commands"
    for command in commands:
        tokens = command.split()
        assert tokens[0] == "hebb", f"unexpected executable: {command!r}"
        assert _resolve_command(tokens[1:]), f"unresolved command: {command!r}"


def test_codex_hook_commands_resolve() -> None:
    """Every command in the Codex hooks manifest is a real CLI command."""
    commands = _extract_hook_commands(CODEX_HOOKS_JSON)
    assert commands, "hooks.json declared no hook commands"
    for command in commands:
        tokens = command.split()
        assert tokens[0] == "hebb", f"unexpected executable: {command!r}"
        assert _resolve_command(tokens[1:]), f"unresolved command: {command!r}"


def test_dockerfile_cmd_references_real_serve_command() -> None:
    """The Dockerfile CMD chain only invokes registered ``hebb`` commands."""
    text = DOCKERFILE.read_text()
    cmd_line = next(
        (line for line in text.splitlines() if line.lstrip().startswith("CMD")),
        None,
    )
    assert cmd_line is not None, "no CMD line found in Dockerfile"
    # The serve entrypoint is what actually starts the server.
    assert "hebb _serve" in cmd_line
    assert "hebb start" not in cmd_line, "nonexistent 'hebb start' still present"
    for tokens in _hebb_invocations(cmd_line):
        if not tokens:
            continue
        assert _resolve_command(tokens), f"unresolved CMD command: {tokens}"
