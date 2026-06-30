"""Parse Codex rollout JSONL into memory-ready turn summaries."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hebb.ingest.noise import clean_user_input, is_greeting_only
from hebb.integrations.claude_code.transcript import TurnSummary

logger = logging.getLogger(__name__)

_MAX_USER_LEN = 500
_MAX_ASSISTANT_LEN = 800
_MIN_USER_LEN = 10


@dataclass
class CodexTurn:
    """A parsed Codex turn and its source timestamp."""

    summary: TurnSummary
    timestamp: str | None = None


def extract_last_turn(
    transcript_path: str | Path,
    *,
    last_assistant_message: str | None = None,
) -> CodexTurn | None:
    """Extract the final user-to-assistant turn from a Codex rollout.

    Args:
        transcript_path: Path to a Codex rollout JSONL file.
        last_assistant_message: Stable assistant text supplied by the Codex
            ``Stop`` hook. When present, it takes precedence over transcript
            assistant records.

    Returns:
        Parsed turn with timestamp, or ``None`` when no complete turn exists.

    Raises:
        OSError: If the transcript cannot be read.
    """
    records = _load_records(Path(transcript_path))
    user_indices = [index for index, record in enumerate(records) if _raw_user_text(record)]
    if not user_indices:
        return None

    user_index = user_indices[-1]
    user_record = records[user_index]
    user_text = _clean_user_text(_raw_user_text(user_record))
    if not user_text:
        return None

    trailing = records[user_index + 1 :]
    assistant_text = _normalize_assistant(last_assistant_message or "")
    if not assistant_text:
        for record in reversed(trailing):
            candidate = _raw_assistant_text(record)
            if candidate:
                assistant_text = _normalize_assistant(candidate)
                break
    if not assistant_text:
        return None

    tools: list[str] = []
    mcps: list[str] = []
    for record in trailing:
        name = _tool_name(record)
        if not name:
            continue
        if name.startswith("mcp__"):
            mcps.append(name)
        else:
            tools.append(name)

    summary = TurnSummary(
        user_input=user_text,
        assistant_output=assistant_text,
        tools=_dedup(tools),
        mcps=_dedup(mcps),
        turn=len(user_indices) - 1,
    )
    timestamp = user_record.get("timestamp")
    return CodexTurn(summary=summary, timestamp=timestamp if isinstance(timestamp, str) else None)


def _load_records(path: Path) -> list[dict[str, Any]]:
    """Load valid JSON object records from a rollout file."""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def _payload(record: dict[str, Any]) -> dict[str, Any]:
    """Return a record payload as a mapping."""
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def _message_text(record: dict[str, Any], *, role: str, block_type: str) -> str:
    """Extract text blocks from a Codex response-item message."""
    if record.get("type") != "response_item":
        return ""
    payload = _payload(record)
    if payload.get("type") != "message" or payload.get("role") != role:
        return ""
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    texts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == block_type and isinstance(block.get("text"), str)
    ]
    return "\n".join(texts).strip()


def _raw_user_text(record: dict[str, Any]) -> str:
    """Return human input text from a Codex message record."""
    return _message_text(record, role="user", block_type="input_text")


def _raw_assistant_text(record: dict[str, Any]) -> str:
    """Return assistant output text from a Codex message record."""
    return _message_text(record, role="assistant", block_type="output_text")


def _tool_name(record: dict[str, Any]) -> str:
    """Return a function-call name from a Codex response item."""
    if record.get("type") != "response_item":
        return ""
    payload = _payload(record)
    if payload.get("type") != "function_call":
        return ""
    name = payload.get("name")
    return name if isinstance(name, str) else ""


def _clean_user_text(raw: str) -> str:
    """Apply Hebb's storage filter and length bound to Codex user text."""
    cleaned = clean_user_input(raw)
    if not cleaned:
        return ""
    if not is_greeting_only(cleaned) and len(cleaned) < _MIN_USER_LEN:
        return ""
    return _truncate(cleaned, _MAX_USER_LEN)


def _normalize_assistant(raw: str) -> str:
    """Normalize and bound assistant output."""
    return _truncate(raw.strip(), _MAX_ASSISTANT_LEN)


def _truncate(value: str, limit: int) -> str:
    """Truncate text with a visible ellipsis."""
    return value if len(value) <= limit else value[:limit] + "…"


def _dedup(items: list[str]) -> list[str]:
    """Remove duplicate strings while preserving order."""
    return list(dict.fromkeys(items))
