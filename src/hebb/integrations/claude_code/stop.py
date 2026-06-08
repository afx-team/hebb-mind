"""Stop hook — record last turn as a single memory."""

from __future__ import annotations

import logging

import httpx

from hebb.integrations._project import detect_project_name
from hebb.integrations.claude_code._client import (
    get_client,
    read_hook_input,
    resolve_session_id,
)
from hebb.integrations.claude_code.transcript import (
    extract_last_turn,
    format_turn_memory,
)

logger = logging.getLogger(__name__)

_PARTITION = "mem_hippocampus"
# How many most-recent memories in the partition to scan for a same-session,
# same-turn duplicate before writing. A re-fired Stop for the same final turn
# lands among the newest writes (the list endpoint returns created_at DESC),
# so a small recent window is enough to catch it without listing everything.
_DEDUP_SCAN_LIMIT = 50


def handle() -> None:
    """Record the last completed turn (user prompt + assistant response).

    Consolidation runs on its own schedule via ``consolidation_time`` in the
    server lifecycle and is not triggered here.
    """
    hook_input = read_hook_input()
    transcript_path = hook_input.get("transcript_path", "")
    if not transcript_path:
        return

    session_id = resolve_session_id(hook_input)
    project = detect_project_name(hook_input.get("cwd"))

    try:
        client = get_client(timeout=30)
    except Exception:
        logger.debug("Could not connect to hebb service", exc_info=True)
        return

    try:
        _record_turn(client, transcript_path, session_id, project)
    finally:
        client.close()


def _record_turn(client: httpx.Client, transcript_path: str, session_id: str, project: str | None) -> None:
    """Extract last turn from transcript and write it as a memory."""
    try:
        summary = extract_last_turn(transcript_path)
    except Exception:
        logger.debug("Transcript parsing failed", exc_info=True)
        return

    if summary is None:
        return

    # Skip turns where the user contributed nothing storable. The user
    # text has already passed through ``_extract_user_text`` /
    # ``_is_storable_user_text``; an empty result here means the prompt
    # filtered down to only pasted code or system noise (greetings and
    # acknowledgements are kept as feedback and do NOT empty out). We
    # intentionally drop the assistant output too in that case: a
    # stand-alone assistant reply with no user context is hard to
    # retrieve usefully.
    if not summary.user_input:
        return

    content = format_turn_memory(summary, session_id=session_id)
    if not content:
        return

    tags = [project] if project else []

    metadata: dict[str, object] = {
        "session_id": session_id,
        "tools": summary.tools,
        "mcps": summary.mcps,
    }
    # Stamp the turn index so successive Stop writes for one session stay
    # ordered for session consolidation and can anchor turn-window expansion.
    if summary.turn is not None:
        metadata["turn"] = summary.turn

    # Idempotency: a Stop event can re-fire for the same final turn (e.g. the
    # host retries the hook). Without a guard each re-fire would create a
    # duplicate memory. When the turn index is known, skip the write if a
    # memory for this session_id+turn already exists.
    if summary.turn is not None and _already_written(client, session_id, summary.turn):
        logger.debug("Turn already recorded (session=%s turn=%s); skipping", session_id, summary.turn)
        return

    try:
        resp = client.post(
            "/api/v1/memories",
            json={
                "content": content,
                "partition_id": _PARTITION,
                "importance_score": 4.0,
                "tags": tags,
                "metadata": metadata,
                "source": "hook:stop",
            },
        )
        resp.raise_for_status()
        logger.debug("Turn summary recorded")
    except Exception:
        logger.debug("Turn summary write failed", exc_info=True)


def _already_written(client: httpx.Client, session_id: str, turn: int) -> bool:
    """Return whether a memory for this session_id+turn was already written.

    Scans the most-recent slice of the hook partition (newest first) for a
    Stop write carrying the same ``session_id`` and ``turn`` metadata. A
    re-fired Stop for the same final turn lands among the newest writes, so
    the recent window catches it. Any failure (service down, response drift)
    is swallowed and reported as "not written" — the guard must never block a
    genuine write or raise out of the hook.

    Args:
        client: An open HTTP client for the Hebb Mind REST API.
        session_id: Session identifier stamped on Stop writes.
        turn: 0-based turn index stamped on Stop writes.

    Returns:
        ``True`` if a matching memory is found, ``False`` otherwise (including
        on any error).
    """
    if not session_id:
        return False
    try:
        resp = client.get(
            "/api/v1/memories",
            params={"partition_id": _PARTITION, "limit": _DEDUP_SCAN_LIMIT},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.debug("Duplicate-turn check failed; proceeding with write", exc_info=True)
        return False

    for item in data.get("items", []) or []:
        meta = item.get("metadata") or {}
        if meta.get("session_id") == session_id and meta.get("turn") == turn:
            return True
    return False
