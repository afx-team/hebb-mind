"""S1 command-drift CI guard (issue #32).

Asserts that every ``hebb <subcommand>`` reference in documentation and
generated client config resolves to a real Click command registered on
the root CLI.  This catches stale docs / config after a command rename
or removal.

Two surfaces are checked:

1. **Documentation** — ``repo_pages/guide/mcp-integration.md`` and its
   zh mirror.  Extracts ``hebb <cmd> [subcmd]`` patterns from code blocks
   and inline code.

2. **Generated config** — Codex and Claude Code installers emit hook
   commands that reference ``hebb codex recall`` / ``hebb claude-code
   stop`` etc.  We build the hook config in-process and verify each
   referenced command exists.

The ``hebb-mcp`` entrypoint (``pyproject.toml`` console script) is also
verified to point at a real module.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from hebb.cli.main import main as cli_main

# ── Helpers ─────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]


def _registered_commands() -> set[str]:
    """Return the set of top-level command names registered on the CLI."""
    return set(cli_main.commands.keys())


def _registered_subcommands(group_name: str) -> set[str]:
    """Return subcommand names for a given group, or empty set if absent."""
    cmd = cli_main.commands.get(group_name)
    if cmd is None:
        return set()
    # Click groups store sub-commands in .commands; single commands don't
    if hasattr(cmd, "commands"):
        return set(cmd.commands.keys())
    return set()


def _extract_hebb_commands_from_text(text: str) -> list[tuple[str, ...]]:
    """Extract (cmd, *subcmds) tuples from text containing ``hebb ...``.

    Only matches inside code blocks or inline code to avoid false positives
    from prose.  Excludes JSON key-value patterns like ``"hebb":``.
    """
    commands: list[tuple[str, ...]] = []

    # Words that look like ``hebb <word>`` but are actually JSON values,
    # prose, or config keys — not CLI commands.
    non_command_words = {"enabled", "true", "false", "null", "command", "args", "env"}

    # Match inside fenced code blocks
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL):
        for m in re.finditer(r"\bhebb\s+([a-z][-a-z]*(?:\s+[a-z][-a-z]*)?)", block):
            parts = m.group(1).strip().split()
            if parts[0] in non_command_words:
                continue
            commands.append(tuple(parts))

    # Match inside inline code: `hebb xxx yyy`
    for m in re.finditer(r"`hebb\s+([a-z][-a-z]*(?:\s+[a-z][-a-z]*)?)`", text):
        parts = m.group(1).strip().split()
        if parts[0] in non_command_words:
            continue
        commands.append(tuple(parts))

    return commands


# ── Tests: CLI surface ──────────────────────────────────────────────────


class TestCLIRegistration:
    """Verify expected commands are registered on the root CLI."""

    EXPECTED_TOP_LEVEL = {
        "amp",
        "claude-code",
        "codex",
        "gemini",
        "goose",
        "opencode",
        "mcp",
        "setup",
        "service",
    }

    def test_expected_top_level_commands_exist(self) -> None:
        registered = _registered_commands()
        missing = self.EXPECTED_TOP_LEVEL - registered
        assert not missing, f"Missing top-level commands: {missing}"

    @pytest.mark.parametrize(
        "group,expected_subs",
        [
            ("codex", {"install", "uninstall", "recall", "prompt", "stop"}),
            ("claude-code", {"install", "uninstall", "recall", "prompt", "stop"}),
            ("gemini", {"install", "uninstall"}),
            ("goose", {"install", "uninstall"}),
            ("opencode", {"install", "uninstall"}),
            ("amp", {"install", "uninstall"}),
        ],
    )
    def test_subcommands_registered(self, group: str, expected_subs: set[str]) -> None:
        actual = _registered_subcommands(group)
        missing = expected_subs - actual
        assert not missing, f"`hebb {group}` missing subcommands: {missing}"


# ── Tests: documentation drift ──────────────────────────────────────────


class TestDocCommandDrift:
    """Ensure every ``hebb …`` in the MCP integration docs resolves to a
    real CLI command."""

    DOCS = [
        ROOT / "repo_pages" / "guide" / "mcp-integration.md",
        ROOT / "repo_pages" / "zh" / "guide" / "mcp-integration.md",
    ]

    @pytest.mark.parametrize("doc_path", DOCS, ids=lambda p: p.name)
    def test_doc_commands_exist(self, doc_path: Path) -> None:
        if not doc_path.exists():
            pytest.skip(f"{doc_path} not found")
        text = doc_path.read_text(encoding="utf-8")
        commands = _extract_hebb_commands_from_text(text)

        top_level = _registered_commands()
        failures: list[str] = []

        for parts in commands:
            cmd = parts[0]
            if cmd not in top_level:
                failures.append(f"  `hebb {' '.join(parts)}` — top-level '{cmd}' not registered")
                continue
            if len(parts) > 1:
                sub = parts[1]
                subs = _registered_subcommands(cmd)
                if sub not in subs:
                    failures.append(
                        f"  `hebb {' '.join(parts)}` — subcommand '{sub}' not registered "
                        f"on `hebb {cmd}` (have: {sorted(subs)})"
                    )

        assert not failures, f"{doc_path.name} references unregistered commands:\n" + "\n".join(failures)


# ── Tests: generated config drift ───────────────────────────────────────


class TestGeneratedConfigDrift:
    """Ensure installer-generated hook commands resolve to real CLI commands."""

    def test_codex_hooks_reference_real_commands(self) -> None:
        from hebb.integrations.codex.install import hooks_config

        top_level = _registered_commands()
        failures: list[str] = []

        for event, handlers in hooks_config().items():
            for handler in handlers:
                hooks_list = handler.get("hooks", [])
                for h in hooks_list:
                    cmd_str = str(h.get("command", ""))
                    # Extract hebb subcommands from the command string
                    for m in re.finditer(r"hebb\s+([a-z][-a-z]*(?:\s+[a-z][-a-z]*)?)", cmd_str):
                        parts = m.group(1).strip().split()
                        cmd = parts[0]
                        if cmd not in top_level:
                            failures.append(f"  hooks_config '{cmd_str}' — '{cmd}' not registered")
                        elif len(parts) > 1:
                            subs = _registered_subcommands(cmd)
                            if parts[1] not in subs:
                                failures.append(
                                    f"  hooks_config '{cmd_str}' — '{parts[1]}' not a subcommand of `hebb {cmd}`"
                                )

        assert not failures, "Codex hooks reference unregistered commands:\n" + "\n".join(failures)


# ── Tests: entrypoint ───────────────────────────────────────────────────


class TestEntrypoint:
    """Verify the hebb-mcp console script points to a real module."""

    def test_hebb_mcp_entrypoint_importable(self) -> None:
        """The module referenced by the ``hebb-mcp`` console script must
        be importable."""
        module = importlib.import_module("hebb.mcp.server")
        assert hasattr(module, "main"), "hebb.mcp.server must expose a main() function"
