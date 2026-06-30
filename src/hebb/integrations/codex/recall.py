"""Codex SessionStart and UserPromptSubmit memory recall hooks."""

from __future__ import annotations


def handle_session_start() -> None:
    """Recall general cross-session context for Codex SessionStart."""
    from hebb.integrations.claude_code.recall import handle

    handle()


def handle_prompt() -> None:
    """Recall prompt-relevant context for Codex UserPromptSubmit."""
    from hebb.integrations.claude_code.recall import handle_prompt as recall_prompt

    recall_prompt()
