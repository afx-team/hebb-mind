"""Parse Claude Code session transcript to extract turn summaries.

Claude Code writes each session as a JSONL file.  Each line is a JSON
object with a ``type`` field (``user``, ``assistant``, ``system``, …).

Message bodies live under ``message.content`` — a list of typed blocks:

- ``{"type": "text", "text": "..."}``              → user / assistant text
- ``{"type": "tool_use", "name": "Read", ...}``    → tool invocation
- ``{"type": "tool_result", ...}``                  → tool output (in user msgs)

MCP tools follow the naming convention ``mcp__<server>__<tool>``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hebb.ingest.noise import strip_noise

logger = logging.getLogger(__name__)

# Truncation limits (characters) for the stored summary.
_MAX_USER_LEN = 500
_MAX_ASSISTANT_LEN = 800


@dataclass
class TurnSummary:
    """Condensed record of a single conversation turn."""

    user_input: str = ""
    assistant_output: str = ""
    tools: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)


def extract_last_turn(transcript_path: str | Path) -> TurnSummary | None:
    """Extract the last user→assistant turn from a Claude Code JSONL transcript.

    Args:
        transcript_path: Path to the session ``.jsonl`` file.

    Returns:
        A ``TurnSummary`` or ``None`` if the transcript cannot be read or
        contains no complete turn.
    """
    path = Path(transcript_path)
    if not path.is_file():
        logger.debug("Transcript not found: %s", path)
        return None

    messages: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        logger.debug("Could not read transcript: %s", path, exc_info=True)
        return None

    if not messages:
        return None

    # Walk backwards to find the last assistant message, then the user
    # message that precedes it.
    last_assistant: dict[str, Any] | None = None
    last_user: dict[str, Any] | None = None

    for msg in reversed(messages):
        msg_type = msg.get("type", "")
        if msg_type == "assistant" and last_assistant is None:
            last_assistant = msg
        elif msg_type == "user" and last_assistant is not None:
            last_user = msg
            break

    if last_assistant is None:
        return None

    summary = TurnSummary()

    # --- User input ---
    if last_user is not None:
        summary.user_input = _extract_user_text(last_user)

    # --- Assistant output & tools ---
    _extract_assistant(last_assistant, summary)

    # Also collect tools from *all* assistant messages in this turn
    # (between last_user and end of transcript).
    if last_user is not None:
        user_idx = messages.index(last_user)
        for msg in messages[user_idx + 1 :]:
            if msg.get("type") == "assistant" and msg is not last_assistant:
                _extract_assistant(msg, summary, text=False)

    # Deduplicate tool lists while preserving order.
    summary.tools = _dedup(summary.tools)
    summary.mcps = _dedup(summary.mcps)

    return summary


def format_turn_memory(summary: TurnSummary, session_id: str = "") -> str:
    """Format a ``TurnSummary`` as a concise memory string.

    Args:
        summary: The turn summary to format.
        session_id: Optional session identifier.

    Returns:
        A human-readable string suitable for storing as a memory.
    """
    parts: list[str] = []

    if summary.user_input:
        parts.append(f"[User] {summary.user_input}")

    if summary.assistant_output:
        parts.append(f"[Assistant] {summary.assistant_output}")

    if summary.tools:
        parts.append(f"[Tools] {', '.join(summary.tools)}")

    if summary.mcps:
        parts.append(f"[MCP] {', '.join(summary.mcps)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_user_text(msg: dict[str, Any]) -> str:
    """Pull plain-text from a user message, stripping system noise."""
    content = msg.get("message", {}).get("content", [])
    texts: list[str] = []
    for block in _iter_blocks(content):
        if block.get("type") == "text":
            texts.append(block.get("text", ""))
    raw = "\n".join(texts).strip()
    cleaned = strip_noise(raw)
    if len(cleaned) > _MAX_USER_LEN:
        cleaned = cleaned[:_MAX_USER_LEN] + "…"
    return cleaned


def _extract_assistant(msg: dict[str, Any], summary: TurnSummary, *, text: bool = True) -> None:
    """Extract text and tool names from an assistant message into *summary*."""
    content = msg.get("message", {}).get("content", [])
    texts: list[str] = []

    for block in _iter_blocks(content):
        block_type = block.get("type", "")

        if block_type == "text" and text:
            texts.append(block.get("text", ""))

        elif block_type in ("tool_use", "server_tool_use"):
            name = block.get("name", "")
            if not name:
                continue
            if name.startswith("mcp__"):
                summary.mcps.append(name)
            else:
                summary.tools.append(name)

    if text and texts:
        raw = "\n".join(texts).strip()
        if len(raw) > _MAX_ASSISTANT_LEN:
            raw = raw[:_MAX_ASSISTANT_LEN] + "…"
        summary.assistant_output = raw


def _iter_blocks(content: Any) -> list[dict[str, Any]]:
    """Normalize content to a list of block dicts."""
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _dedup(items: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
