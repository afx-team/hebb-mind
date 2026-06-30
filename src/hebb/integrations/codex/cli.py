"""Codex CLI integration commands."""

from __future__ import annotations

import shutil

import click


@click.group("codex")
def codex() -> None:
    """Codex integration — native MCP and lifecycle hooks."""


@codex.command("install")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    show_default=True,
    help=(
        "Where to install: 'project' writes this repo's .codex/ config; "
        "'user' writes the current user's global Codex config for all projects."
    ),
)
def install(scope: str) -> None:
    """Install Hebb Mind MCP and lifecycle hooks into Codex.

    Project scope writes ``.codex/config.toml`` and ``.codex/hooks.json``.
    User scope registers MCP through ``codex mcp add`` and writes the user
    hooks file.
    """
    _ensure_codex()

    from hebb.integrations.codex.install import handle

    handle(scope)


@codex.command("uninstall")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    show_default=True,
    help=(
        "Where to remove from: 'project' removes this repo's .codex/ config; "
        "'user' removes the current user's global Codex config."
    ),
)
def uninstall(scope: str) -> None:
    """Remove Hebb Mind MCP and lifecycle hooks from Codex."""
    _ensure_codex()

    from hebb.integrations.codex.uninstall import handle

    handle(scope)


@codex.command("recall")
def recall() -> None:
    """Recall cross-session memories for a Codex SessionStart hook."""
    from hebb.integrations.codex.recall import handle_session_start

    handle_session_start()


@codex.command("prompt")
def prompt() -> None:
    """Recall prompt-relevant memories for a UserPromptSubmit hook."""
    from hebb.integrations.codex.recall import handle_prompt

    handle_prompt()


@codex.command("stop")
def stop() -> None:
    """Record the completed Codex turn from a Stop hook."""
    from hebb.integrations.codex.stop import handle

    handle()


def _ensure_codex() -> None:
    """Raise a user-facing error when the Codex CLI is unavailable."""
    if not shutil.which("codex"):
        raise click.ClickException("codex CLI not found on PATH")
