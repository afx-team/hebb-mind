"""Per-format conversation parsers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from hippocampus.ingest.types import NormalizedTurn

# Role mapping for various message type strings.
_ROLE_MAP: dict[str, str] = {
    "human": "user",
    "user": "user",
    "assistant": "assistant",
    "ai": "assistant",
    "tool_use": "tool",
    "tool_result": "tool",
    "system": "system",
}

# Plain-text role markers.
_ROLE_MARKER_RE = re.compile(
    r"^(user|assistant|system|human|ai)\s*:\s*(.*)$",
    re.IGNORECASE,
)


def parse_claude_code_jsonl(raw: str) -> list[NormalizedTurn]:
    """Parse Claude Code JSONL conversation export.

    Each line is a JSON object with ``type``/``role``, ``content``,
    optional ``session_id`` and ``timestamp``.  Tool use/result lines
    are collapsed into the preceding assistant turn.

    Args:
        raw: JSONL string with one message per line.

    Returns:
        List of NormalizedTurn objects.
    """
    turns: list[NormalizedTurn] = []
    session_id: str | None = None
    turn_idx = 0

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_type = obj.get("type", obj.get("role", ""))
        content = obj.get("content", "")
        ts = obj.get("timestamp", obj.get("created_at"))
        sid = obj.get("session_id", obj.get("conversation_id"))
        if sid:
            session_id = str(sid)

        text = _extract_text(content)
        if not text:
            continue

        role = _ROLE_MAP.get(msg_type.lower(), "user") if msg_type else "user"

        # Collapse tool results into previous assistant turn
        if role == "tool" and turns and turns[-1].role == "assistant":
            turns[-1].content += f"\n[Tool result]: {text}"
            continue

        turns.append(
            NormalizedTurn(
                role=role,
                content=text,
                session_id=session_id,
                turn_index=turn_idx,
                timestamp=str(ts) if ts else None,
            )
        )
        turn_idx += 1

    return turns


def parse_chatgpt_json(raw: str) -> list[NormalizedTurn]:
    """Parse ChatGPT ``conversations.json`` export.

    The export is an array of conversation objects.  Each has a
    ``mapping`` dict where values contain ``message`` objects with
    ``author.role`` and ``content.parts``.

    Args:
        raw: JSON string of ChatGPT export.

    Returns:
        List of NormalizedTurn objects.
    """
    data = json.loads(raw)
    conversations = data if isinstance(data, list) else [data]

    turns: list[NormalizedTurn] = []
    for conv in conversations:
        conv_id = conv.get("id", conv.get("conversation_id"))
        mapping = conv.get("mapping", {})

        # Collect messages and sort by create_time
        messages: list[tuple[float, dict]] = []
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            parts = msg.get("content", {}).get("parts")
            if not parts:
                continue
            messages.append((msg.get("create_time", 0) or 0, msg))

        messages.sort(key=lambda x: x[0])

        for idx, (ts, msg) in enumerate(messages):
            role = msg.get("author", {}).get("role", "unknown")
            parts = msg.get("content", {}).get("parts", [])
            text = " ".join(str(p) for p in parts if isinstance(p, str)).strip()
            if not text or role == "system":
                continue

            turns.append(
                NormalizedTurn(
                    role=_ROLE_MAP.get(role, role),
                    content=text,
                    session_id=str(conv_id) if conv_id else None,
                    turn_index=idx,
                    timestamp=_format_ts(ts) if ts else None,
                )
            )

    return turns


def parse_plain_text(raw: str) -> list[NormalizedTurn]:
    """Parse plain text with optional role markers.

    Recognises ``User: ...`` / ``Assistant: ...`` markers
    (case-insensitive) and ``> ...`` lines as user input.
    Unmarked text defaults to ``user``.

    Args:
        raw: Plain text string.

    Returns:
        List of NormalizedTurn objects.
    """
    lines = raw.strip().split("\n")
    turns: list[NormalizedTurn] = []
    current_role: str | None = None
    current_content: list[str] = []
    turn_idx = 0

    def _flush() -> None:
        nonlocal turn_idx
        if current_role and current_content:
            text = "\n".join(current_content).strip()
            if text:
                turns.append(
                    NormalizedTurn(
                        role=_ROLE_MAP.get(current_role.lower(), current_role.lower()),
                        content=text,
                        turn_index=turn_idx,
                    )
                )
                turn_idx += 1

    for line in lines:
        line = line.rstrip()

        # Role marker
        match = _ROLE_MARKER_RE.match(line)
        if match:
            _flush()
            current_role = match.group(1)
            current_content = [match.group(2)] if match.group(2) else []
            continue

        # > marker (user input)
        if line.startswith("> "):
            if current_role and current_role.lower() not in ("user", "human"):
                _flush()
                current_content = []
            current_role = "user"
            current_content.append(line[2:])
            continue

        # Continuation
        if current_role:
            current_content.append(line)
        else:
            current_role = "user"
            current_content.append(line)

    _flush()
    return turns


# -- Helpers ------------------------------------------------------------------


def _extract_text(content: str | list | dict) -> str:
    """Extract plain text from various content representations."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "\n".join(parts)
    if isinstance(content, dict) and "text" in content:
        return content["text"]
    return ""


def _format_ts(ts: float | int) -> str:
    """Convert a Unix timestamp to ISO 8601."""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return ""
