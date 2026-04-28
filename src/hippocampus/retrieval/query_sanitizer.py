"""Query sanitization for LLM-generated search queries."""

from __future__ import annotations

import re

# Maximum query length after sanitization.
MAX_QUERY_LEN = 500

# Known MCP / LLM system tags (whitelist — avoids stripping legitimate angle brackets).
_KNOWN_TAGS_RE = re.compile(
    r"</?(?:system-reminder|command-message|command|tool_call|function_call|"
    r"tool_result|function_result|context|thinking|antThinking|response|"
    r"result|output|input|search_query|artifact|user-request|"
    r"environment_details|hook_chrome|tool_response)[^>]*>",
    re.IGNORECASE,
)

# Fenced code blocks.
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

# JSON blobs that look like tool calls.
_JSON_TOOL_RE = re.compile(r"\{[^{}]*\"(?:type|name|tool|function)\"[^{}]*\}")

# Question sentence — starts with upper-case, ends with ?
_QUESTION_RE = re.compile(
    r"(?:^|(?<=\.\s)|(?<=\?\s)|(?<=\n)|(?<=\s))([A-Z][^.!?\n]{10,}\?)",
    re.MULTILINE,
)

# Intent prefixes signalling the real search query.
_INTENT_RE = re.compile(
    r"(?:^|\n|(?<=\.\s)|(?<=\s))(?:find|search|look\s+up|retrieve|recall|"
    r"what|when|where|who|how|why|which|tell\s+me|show\s+me|get|list)\b",
    re.IGNORECASE,
)


def sanitize_query(raw: str) -> str:
    """Clean an LLM-generated query for embedding and keyword search.

    Four-step cascade:
        1. Passthrough — short, clean queries returned as-is.
        2. Strip noise — remove XML tags, code fences, JSON artifacts.
        3. Extract question — find the actual question sentence.
        4. Tail truncation — fallback: last *MAX_QUERY_LEN* chars at a
           sentence boundary.

    Args:
        raw: Raw query string from MCP tool or API.

    Returns:
        Cleaned query suitable for retrieval.
    """
    if not raw or not raw.strip():
        return raw

    text = raw.strip()

    # Step 1: passthrough for short, clean queries (no tags, no fences, no JSON tools)
    if len(text) <= 200 and not _KNOWN_TAGS_RE.search(text) and "```" not in text and not _JSON_TOOL_RE.search(text):
        return text

    # Step 2: strip noise
    cleaned = _strip_xml_tags(text)
    cleaned = _strip_tool_artifacts(cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return text[:MAX_QUERY_LEN]

    # Short enough after cleanup? Return directly.
    if len(cleaned) <= MAX_QUERY_LEN:
        return cleaned

    # Step 3: try to extract a question
    question = _extract_question(cleaned)
    if question:
        return question[:MAX_QUERY_LEN]

    # Step 3b: try to find an intent sentence
    intent = _extract_intent(cleaned)
    if intent:
        return intent[:MAX_QUERY_LEN]

    # Step 4: fallback — tail truncation at sentence boundary
    return _truncate_to_tail(cleaned, MAX_QUERY_LEN)


def _strip_xml_tags(text: str) -> str:
    """Remove known MCP / LLM system tags.

    Only removes tags from a whitelist to avoid stripping legitimate
    angle brackets (e.g. ``x < 5``).

    Args:
        text: Input text.

    Returns:
        Text with known tags removed.
    """
    return _KNOWN_TAGS_RE.sub("", text)


def _strip_tool_artifacts(text: str) -> str:
    """Remove code fences and JSON tool-call blobs.

    Args:
        text: Input text.

    Returns:
        Text with artifacts removed.
    """
    result = _CODE_BLOCK_RE.sub("", text)
    result = _JSON_TOOL_RE.sub("", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"  +", " ", result)
    return result


def _extract_question(text: str) -> str | None:
    """Find the actual question sentence in noisy text.

    Returns the *last* match (most likely the real query when preceded
    by preamble).

    Args:
        text: Cleaned text.

    Returns:
        Question string, or *None*.
    """
    matches = _QUESTION_RE.findall(text)
    return matches[-1].strip() if matches else None


def _extract_intent(text: str) -> str | None:
    """Find a sentence starting with a query-intent prefix.

    Args:
        text: Cleaned text.

    Returns:
        The intent sentence, or *None*.
    """
    match = _INTENT_RE.search(text)
    if not match:
        return None
    rest = text[match.start() :].strip()
    end = re.search(r"[.!?\n]", rest[1:])
    if end:
        return rest[: end.start() + 2].strip()
    return rest.strip()


def _truncate_to_tail(text: str, max_chars: int) -> str:
    """Return the last *max_chars* of *text*, aligned to a sentence boundary.

    Args:
        text: Text to truncate.
        max_chars: Maximum character count.

    Returns:
        Tail portion of the text.
    """
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    sentence_start = re.search(r"(?:^|(?<=\.\s)|(?<=\n))[A-Z]", tail)
    if sentence_start and sentence_start.start() < len(tail) // 2:
        return tail[sentence_start.start() :]
    return tail
