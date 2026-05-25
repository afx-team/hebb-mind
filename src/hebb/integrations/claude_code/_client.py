"""Shared HTTP client and stdin helpers for Claude Code hooks."""

from __future__ import annotations

import json
import logging
import sys

import httpx

from hebb.utils.service import ensure_service_running, resolve_base_url

logger = logging.getLogger(__name__)


def read_hook_input() -> dict:
    """Parse JSON from stdin provided by Claude Code hooks.

    Returns an empty dict on EOF, empty stdin, or malformed JSON.
    """
    try:
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return {}


def get_client(timeout: float = 10) -> httpx.Client:
    """Return a synchronous HTTP client pointing at the Hebb Mind REST API.

    Auto-starts the service if not running.
    """
    ensure_service_running()
    return httpx.Client(base_url=resolve_base_url(), timeout=timeout)
