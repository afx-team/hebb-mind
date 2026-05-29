"""Shared HTTP client and stdin helpers for Claude Code hooks."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from typing import Any, cast

import httpx

from hebb.utils.service import ensure_service_running, resolve_base_url

logger = logging.getLogger(__name__)


def read_hook_input() -> dict[str, Any]:
    """Parse JSON from stdin provided by Claude Code hooks.

    Returns an empty dict on EOF, empty stdin, or malformed JSON.
    """
    try:
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return cast("dict[str, Any]", json.loads(data))
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_session_id(hook_input: dict[str, Any]) -> str:
    """Return a stable session identifier for write/recall correlation.

    Prefers ``hook_input.session_id`` (Claude Code provides this for every
    hook event). When absent — e.g. a custom invocation that only carries
    ``transcript_path`` — derives a deterministic ID from the transcript
    path so the same session always hashes to the same value, which keeps
    the recall-time "filter out my own session" check working.

    Returns ``""`` when neither field is available; callers should treat
    that as "do not filter".
    """
    sid = hook_input.get("session_id", "") or ""
    if sid:
        return sid
    transcript_path = hook_input.get("transcript_path", "") or ""
    if transcript_path:
        return hashlib.sha256(transcript_path.encode()).hexdigest()[:16]
    return ""


def get_client(timeout: float = 10) -> httpx.Client:
    """Return a synchronous HTTP client pointing at the Hebb Mind REST API.

    Auto-starts the service if not running.
    """
    ensure_service_running()
    return httpx.Client(base_url=resolve_base_url(), timeout=timeout)
