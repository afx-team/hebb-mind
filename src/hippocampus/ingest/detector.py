"""Conversation format auto-detection."""

from __future__ import annotations

import json

from hippocampus.ingest.types import Format


def detect_format(raw: str) -> Format:
    """Auto-detect the format of raw conversation data.

    Args:
        raw: Raw input string.

    Returns:
        The detected Format enum value.
    """
    stripped = raw.strip()
    if not stripped:
        return Format.PLAIN_TEXT

    # JSONL: first line is valid JSON with "type" or "role" key
    first_line = stripped.split("\n", 1)[0].strip()
    if first_line.startswith("{"):
        try:
            obj = json.loads(first_line)
            if isinstance(obj, dict) and ("type" in obj or "role" in obj):
                return Format.CLAUDE_CODE_JSONL
        except json.JSONDecodeError:
            pass

    # Full JSON: array or object with "mapping" key (ChatGPT export)
    if stripped.startswith(("{", "[")):
        try:
            data = json.loads(stripped)
            if isinstance(data, list) and data and isinstance(data[0], dict) and "mapping" in data[0]:
                return Format.CHATGPT_JSON
            if isinstance(data, dict) and "mapping" in data:
                return Format.CHATGPT_JSON
        except (json.JSONDecodeError, IndexError, TypeError):
            pass

    return Format.PLAIN_TEXT
