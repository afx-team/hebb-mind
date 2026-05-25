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
