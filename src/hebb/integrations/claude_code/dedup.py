"""Content-hash deduplication for hook writes."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

STATE_DIR = Path.home() / ".hebb"
STATE_FILE = STATE_DIR / "hook_state.json"

_MAX_HASHES_PER_SESSION = 200


def _load_state() -> dict[str, Any]:
    try:
        if STATE_FILE.exists():
            return cast("dict[str, Any]", json.loads(STATE_FILE.read_text()))
    except (json.JSONDecodeError, OSError):
        logger.debug("Could not load hook state, starting fresh")
    return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False))
    except OSError:
        logger.debug("Could not save hook state", exc_info=True)


def content_hash(text: str) -> str:
    """SHA-256 prefix of normalized text."""
    normalized = text.strip().lower()[:500]
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def is_duplicate(session_id: str, text: str) -> bool:
    """Check if this content was already written in the given session."""
    state = _load_state()
    hashes = state.get("sessions", {}).get(session_id, {}).get("hashes", [])
    return content_hash(text) in hashes


def record_written(session_id: str, text: str) -> None:
    """Record that this content was written for dedup tracking."""
    state = _load_state()
    sessions = state.setdefault("sessions", {})
    sess = sessions.setdefault(session_id, {"hashes": []})
    sess["hashes"].append(content_hash(text))
    sess["hashes"] = sess["hashes"][-_MAX_HASHES_PER_SESSION:]
    _save_state(state)


def cleanup_session(session_id: str) -> None:
    """Remove session state after session ends."""
    state = _load_state()
    sessions = state.get("sessions", {})
    if session_id in sessions:
        del sessions[session_id]
        _save_state(state)
