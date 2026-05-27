"""Noise stripping for conversation content."""

from __future__ import annotations

import re

# Paired system tags — strip the entire block (opening tag + content + closing tag).
_SYSTEM_BLOCK_RE = re.compile(
    r"<(system-reminder|local-command-stdout|local-command-caveat|"
    r"environment_details|hook_chrome|thinking|antThinking|"
    r"command-name|command-args|command-message)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Remaining unpaired / self-closing system tags.
_SYSTEM_TAG_RE = re.compile(
    r"</?(?:system|system-reminder|hook_chrome|environment_details|"
    r"tool_response|command|command-name|command-args|command-message|"
    r"local-command-stdout|local-command-caveat|thinking|antThinking)[^>]*>",
    re.IGNORECASE,
)

# Environment info lines (Platform, Shell, etc.).
_ENV_LINE_RE = re.compile(
    r"^(?:Current working directory|Platform|Shell|OS Version|"
    r"Current date|Git user|Status):\s*[^\n]+$",
    re.MULTILINE,
)

# Three or more consecutive newlines.
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

# Fenced code blocks: ```lang\n...\n``` OR inline ```...```. DOTALL so multi-
# line bodies match. Both the fence and the body are dropped from user input
# because pasted code rarely carries the semantic intent of the question —
# the surrounding prose does.
_CODE_FENCE_RE = re.compile(r"```[^\n`]*\n.*?```", re.DOTALL)
_INLINE_CODE_FENCE_RE = re.compile(r"```[^`\n]+?```")

# Greeting / acknowledgement messages that are pure social signaling with no
# memorable content. Matched as the *entire* normalized message (after lowercase
# + edge-punctuation strip), so substantive prompts that merely start with
# "hi, ..." are unaffected.
_GREETINGS: frozenset[str] = frozenset(
    {
        # English social openers / closers
        "hi",
        "hello",
        "hey",
        "yo",
        "sup",
        "howdy",
        "bye",
        "goodbye",
        "cya",
        "see you",
        "see ya",
        "good morning",
        "good night",
        "good afternoon",
        "good evening",
        "morning",
        "afternoon",
        "evening",
        "night",
        # Chinese social openers / closers
        "你好",
        "您好",
        "嗨",
        "哈喽",
        "哈罗",
        "早",
        "早上好",
        "中午好",
        "下午好",
        "晚上好",
        "晚安",
        "再见",
        "拜拜",
        "拜",
        "回见",
    }
)


def strip_noise(text: str) -> str:
    """Remove system tags, UI artifacts, and environment info from conversation content.

    Args:
        text: Raw conversation content.

    Returns:
        Cleaned text with noise removed.
    """
    if not text:
        return text

    # First remove paired blocks (content between tags)
    result = _SYSTEM_BLOCK_RE.sub("", text)
    # Then strip any remaining unpaired tags
    result = _SYSTEM_TAG_RE.sub("", result)
    result = _ENV_LINE_RE.sub("", result)
    result = _MULTI_NEWLINE_RE.sub("\n\n", result)
    return result.strip()


def strip_code_fences(text: str) -> str:
    """Remove fenced code blocks (``` ... ```) along with their content.

    Both multi-line ``` blocks with optional language hints and inline ``code``
    spans wrapped in triple backticks are dropped.
    """
    if not text:
        return text
    result = _CODE_FENCE_RE.sub("", text)
    result = _INLINE_CODE_FENCE_RE.sub("", result)
    return _MULTI_NEWLINE_RE.sub("\n\n", result).strip()


# Paired HTML/XML element with body, then any remaining standalone tag.
# We require a real tag name (``[a-zA-Z][\w-]*``) so chevron-style ASCII
# in user prose ("3 < x < 5") isn't mistaken for HTML.
_HTML_BLOCK_RE = re.compile(r"<([a-zA-Z][\w-]*)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][\w-]*\b[^>]*/?>", re.IGNORECASE)


def strip_html_tags(text: str) -> str:
    """Remove HTML / XML markup from user prose.

    Paired blocks (``<div>…</div>``) are removed entirely (tag + body +
    closer) so big pasted HTML dumps don't survive into memory. Any
    remaining unpaired tags (``<br/>``, ``<img …>``) are then stripped.
    Bare angle-bracket prose without a tag-name pattern is left alone.
    """
    if not text:
        return text
    result = _HTML_BLOCK_RE.sub("", text)
    result = _HTML_TAG_RE.sub("", result)
    return _MULTI_NEWLINE_RE.sub("\n\n", result).strip()


# Data URI prefix (``data:image/png;base64,<blob>``) and bare base64 blobs.
# Threshold of 80 characters of base64 alphabet keeps short alphanumeric
# tokens (UUIDs, short hashes, identifiers) intact.
_DATA_URI_RE = re.compile(r"data:[^,;\s]+;base64,[A-Za-z0-9+/=]+")
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")


def strip_base64_blobs(text: str) -> str:
    """Drop ``data:…;base64,…`` URIs and long bare base64 sequences.

    Long base64 (≥80 chars) typically means a pasted binary — image dump,
    JWT, encoded artifact — that bloats the memory without adding any
    queryable signal.
    """
    if not text:
        return text
    result = _DATA_URI_RE.sub("", text)
    result = _BASE64_BLOB_RE.sub("", result)
    return _MULTI_NEWLINE_RE.sub("\n\n", result).strip()


def clean_user_input(text: str) -> str:
    """Full user-side filter pipeline.

    Composes the individual strippers in the order they're most effective:

        1. ``strip_noise``        — system-tag blocks + env metadata
        2. ``strip_code_fences``  — pasted ```code``` bodies
        3. ``strip_html_tags``    — pasted HTML / XML dumps
        4. ``strip_base64_blobs`` — encoded binary payloads & data URIs

    The result is the prose that's actually worth remembering. Callers
    are expected to apply their own greeting / min-length checks on the
    cleaned output to decide whether the turn is worth storing at all.
    """
    if not text:
        return text
    return strip_base64_blobs(strip_html_tags(strip_code_fences(strip_noise(text))))


def is_greeting_only(text: str) -> bool:
    """True when the message is *purely* a greeting / acknowledgement.

    Comparison is on the normalized form (lowercased, edge punctuation
    stripped) against a curated set. Substantive messages that merely
    begin with a greeting ("hi, can you help with X?") do not match.
    """
    if not text:
        return False
    normalized = text.strip().lower().strip(".,!?~。，！？～ \t\n")
    if not normalized:
        return False
    return normalized in _GREETINGS
