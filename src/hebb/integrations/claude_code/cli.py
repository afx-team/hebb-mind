"""Claude Code CLI subgroup: hebb claude-code {install|uninstall|recall|prompt|stop}."""

from __future__ import annotations

import click


@click.group("claude-code")
def cc() -> None:
    """Claude Code integration — auto write/recall/consolidate hooks."""


@cc.command()
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help="Install scope: project (.claude/) or user (~/.claude/).",
)
def install(scope: str) -> None:
    """Install hebb hooks and MCP server into Claude Code."""
    from hebb.integrations.claude_code.install import handle

    handle(scope)


@cc.command()
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="project",
    help="Uninstall scope: project (.claude/) or user (~/.claude/).",
)
def uninstall(scope: str) -> None:
    """Remove hebb hooks and MCP server from Claude Code."""
    from hebb.integrations.claude_code.uninstall import handle

    handle(scope)


@cc.command()
def recall() -> None:
    """Recall cross-session memories (SessionStart hook)."""
    from hebb.integrations.claude_code.recall import handle

    handle()


@cc.command()
def prompt() -> None:
    """Recall memories relevant to the user's prompt (UserPromptSubmit hook)."""
    from hebb.integrations.claude_code.recall import handle_prompt

    handle_prompt()


@cc.command()
def stop() -> None:
    """Record turn summary (Stop hook)."""
    from hebb.integrations.claude_code.stop import handle

    handle()
