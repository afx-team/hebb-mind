"""Parse Claude Code session transcript to extract turn summaries.

Claude Code writes each session as a JSONL file.  Each line is a JSON
object with a ``type`` field (``user``, ``assistant``, ``system``, …).

Message bodies live under ``message.content`` — a list of typed blocks:

- ``{"type": "text", "text": "..."}``              → user / assistant text
- ``{"type": "tool_use", "name": "Read", ...}``    → tool invocation
- ``{"type": "tool_result", ...}``                  → tool output (in user msgs)

MCP tools follow the naming convention ``mcp__<server>__<tool>``.

Subagent (Task tool) turns are written into the *same* session JSONL as the
main agent, tagged ``"isSidechain": true``. The Stop hook records the human's
turn, so those machine-authored lines are dropped at load time (see
``_is_sidechain``) — otherwise a subagent's task prompt could be stored as the
user input and its tool calls would leak into the turn summary.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hebb.ingest.noise import clean_user_input, is_greeting_only

logger = logging.getLogger(__name__)

# Truncation limits (characters) for the stored summary.
_MAX_USER_LEN = 500
_MAX_ASSISTANT_LEN = 800
# Anything shorter than this *after* noise/code/html/base64 stripping is
# treated as low-signal — too short to be worth a memory slot, even if
# the assistant produced a long reply. Tuned to drop "fix it" / "thanks
# more" while keeping "Why does X fail?" (15 chars) and similar.
_MIN_USER_LEN = 10


@dataclass
class TurnSummary:
    """Condensed record of a single conversation turn."""

    user_input: str = ""
    assistant_output: str = ""
    tools: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)
    # 0-based position of this human turn within the session (count of
    # human-authored user messages up to and including the anchor). Lets the
    # Stop hook stamp metadata.turn so successive Stop writes for one session
    # stay ordered and can anchor turn-window expansion. None if unknown.
    turn: int | None = None


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
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Drop subagent (Task tool) lines: the Stop hook records the
                # human turn, not a subagent's internal turns. Filtering here —
                # the single point where the transcript is loaded — fixes the
                # user-input anchor, the turn index, and the tool/mcp lists at
                # once, since the rest of the parser then only sees main-agent
                # messages.
                if _is_sidechain(obj):
                    continue
                messages.append(obj)
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
            # In a tool-using turn the trailing ``user`` messages are
            # tool_result carriers (role=user, no human text); the actual
            # prompt sits several messages back. Skip carriers so we anchor
            # the turn on the human utterance.
            if not _raw_user_text(msg):
                continue
            last_user = msg
            break

    if last_assistant is None:
        return None

    summary = TurnSummary()

    # Turn index = 0-based position of the anchored human turn within the
    # session (count of human-authored user messages up to and including it).
    # tool_result carriers (role=user, no human text) are filtered by
    # ``_raw_user_text`` so they don't inflate the count.
    if last_user is not None:
        anchor_idx = messages.index(last_user)
        summary.turn = sum(1 for m in messages[: anchor_idx + 1] if m.get("type") == "user" and _raw_user_text(m)) - 1

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


def format_turn_memory(
    summary: TurnSummary,
    session_id: str = "",
    timestamp: str | None = None,
) -> str:
    """Format a ``TurnSummary`` as a concise memory string.

    A bracketed ISO timestamp leads the memory so the LLM can resolve
    relative phrases ("yesterday", "last week", "4 years ago") into
    concrete dates without having to consult metadata it does not see at
    answer-generation time. Without this, every memory looks
    time-of-event-less.

    Args:
        summary: The turn summary to format.
        session_id: Optional session identifier.
        timestamp: ISO-8601 timestamp (default: now in UTC). Pass an
            explicit value when replaying historical turns so the prefix
            reflects when the conversation actually happened.

    Returns:
        A human-readable string suitable for storing as a memory.
    """
    from datetime import datetime, timezone

    ts = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    parts: list[str] = [f"[{ts}]"]

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


def _is_sidechain(msg: dict[str, Any]) -> bool:
    """True when a transcript line belongs to a subagent (Task tool) sidechain.

    Claude Code writes subagent turns into the same session JSONL as the main
    agent, tagged ``"isSidechain": true``. A missing key denotes a main-agent
    line, so legacy transcripts (and every existing fixture) are unaffected.

    Args:
        msg: A parsed transcript line.

    Returns:
        ``True`` if the line is a subagent sidechain message.
    """
    return bool(msg.get("isSidechain", False))


def _is_storable_user_text(cleaned: str) -> bool:
    """Write judgment for the Stop hook's turn recorder.

    Deliberately distinct from the recall hook's ``_is_recall_worthy``:
    storage and recall ask different questions of the same utterance. A
    cleaned user message earns a memory slot when it is either substantive
    prose (>= ``_MIN_USER_LEN``) or a recognized greeting / acknowledgement.
    The latter are short but are collected as feedback, so — unlike the
    recall hook, which skips them — storage keeps them. Everything else
    (empty after noise/code/HTML stripping, or a terse non-social fragment
    like a bare "fix it") is dropped.
    """
    if not cleaned:
        return False
    if is_greeting_only(cleaned):
        return True
    return len(cleaned) >= _MIN_USER_LEN


def _raw_user_text(msg: dict[str, Any]) -> str:
    """Concatenate the human-authored text of a user message.

    Claude Code stores a plain prompt as a bare ``content`` string and a
    richer prompt (attachments, images, slash-command output) as a list of
    typed blocks. Tool output arrives as ``user`` messages whose blocks are
    all ``tool_result`` — those carry no human text and yield ``""``.
    """
    content = msg.get("message", {}).get("content", "")
    if isinstance(content, str):
        return content.strip()
    texts = [b.get("text", "") for b in _iter_blocks(content) if b.get("type") == "text"]
    return "\n".join(texts).strip()


def _extract_user_text(msg: dict[str, Any]) -> str:
    """Pull plain-text from a user message, then run the user-input filter.

    Returns ``""`` when the prompt is not storable per
    ``_is_storable_user_text`` — the Stop hook reads that as "skip this
    turn entirely". Storable prose is cleaned (system tags, code fences,
    HTML, base64 blobs all removed) and truncated to ``_MAX_USER_LEN``.
    """
    cleaned = clean_user_input(_raw_user_text(msg))
    if not _is_storable_user_text(cleaned):
        return ""
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
