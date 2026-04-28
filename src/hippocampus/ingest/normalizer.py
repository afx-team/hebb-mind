"""Conversation normalizer — detect format, parse, and produce normalized turns."""

from __future__ import annotations

from hippocampus.ingest.detector import detect_format
from hippocampus.ingest.formats import (
    parse_chatgpt_json,
    parse_claude_code_jsonl,
    parse_plain_text,
)
from hippocampus.ingest.noise import strip_noise
from hippocampus.ingest.types import Format, IngestResult


def normalize(raw: str, format_hint: str | None = None) -> IngestResult:
    """Detect format, parse, normalize, and clean conversation data.

    Args:
        raw: Raw input string (JSONL, JSON, or plain text).
        format_hint: Optional format override (``'claude_code'``,
            ``'chatgpt'``, ``'plain'``).

    Returns:
        IngestResult with detected format, normalized turns, and warnings.

    Raises:
        ValueError: If *format_hint* is not a recognised format.
    """
    warnings: list[str] = []

    if format_hint:
        try:
            fmt = Format(format_hint)
        except ValueError:
            warnings.append(f"Unknown format_hint '{format_hint}', auto-detecting")
            fmt = detect_format(raw)
    else:
        fmt = detect_format(raw)

    if fmt == Format.CLAUDE_CODE_JSONL:
        turns = parse_claude_code_jsonl(raw)
    elif fmt == Format.CHATGPT_JSON:
        turns = parse_chatgpt_json(raw)
    else:
        turns = parse_plain_text(raw)

    # Apply noise stripping to all turns
    for turn in turns:
        turn.content = strip_noise(turn.content)

    # Filter turns with empty content after cleanup
    turns = [t for t in turns if t.content.strip()]

    return IngestResult(
        format_detected=fmt.value,
        turns=turns,
        turn_count=len(turns),
        warnings=warnings,
    )
