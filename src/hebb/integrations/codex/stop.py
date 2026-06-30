"""Codex Stop hook — record the completed turn as one memory."""

from __future__ import annotations

import logging

import httpx

from hebb.integrations._project import detect_project_name
from hebb.integrations.claude_code._client import (
    get_client,
    read_hook_input,
    resolve_session_id,
)
from hebb.integrations.claude_code.transcript import TurnSummary, format_turn_memory
from hebb.integrations.codex.transcript import extract_last_turn

logger = logging.getLogger(__name__)

_PARTITION = "mem_hippocampus"
_DEDUP_SCAN_LIMIT = 50


def handle() -> None:
    """Record the final Codex turn supplied to a ``Stop`` hook."""
    hook_input = read_hook_input()
    transcript_path = hook_input.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return

    session_id = resolve_session_id(hook_input)
    project = detect_project_name(hook_input.get("cwd"))
    assistant = hook_input.get("last_assistant_message")
    assistant_text = assistant if isinstance(assistant, str) else None

    try:
        turn = extract_last_turn(transcript_path, last_assistant_message=assistant_text)
    except (OSError, ValueError):
        logger.debug("Codex transcript parsing failed", exc_info=True)
        return
    if turn is None:
        return

    try:
        client = get_client(timeout=30)
    except Exception:
        logger.debug("Could not connect to Hebb Mind service", exc_info=True)
        return

    try:
        _record_turn(
            client,
            turn.summary,
            timestamp=turn.timestamp,
            session_id=session_id,
            turn_id=str(hook_input.get("turn_id", "") or ""),
            project=project,
        )
    finally:
        client.close()


def _record_turn(
    client: httpx.Client,
    summary: TurnSummary,
    *,
    timestamp: str | None,
    session_id: str,
    turn_id: str,
    project: str | None,
) -> None:
    """Write one parsed Codex turn unless it was already captured.

    Args:
        client: Connected Hebb Mind HTTP client.
        summary: Parsed turn summary.
        timestamp: User-message timestamp from the rollout.
        session_id: Codex session identifier.
        turn_id: Codex turn identifier.
        project: Detected project tag.
    """
    if summary.turn is not None and _already_written(client, session_id, summary.turn):
        return

    content = format_turn_memory(summary, session_id=session_id, timestamp=timestamp)
    metadata: dict[str, object] = {
        "session_id": session_id,
        "host": "codex",
        "tools": summary.tools,
        "mcps": summary.mcps,
    }
    if summary.turn is not None:
        metadata["turn"] = summary.turn
    if turn_id:
        metadata["turn_id"] = turn_id

    try:
        response = client.post(
            "/api/v1/memories",
            json={
                "content": content,
                "partition_id": _PARTITION,
                "importance_score": 4.0,
                "tags": [project] if project else [],
                "metadata": metadata,
                "source": "hook:codex-stop",
            },
        )
        response.raise_for_status()
    except Exception:
        logger.debug("Codex turn memory write failed", exc_info=True)


def _already_written(client: httpx.Client, session_id: str, turn: int) -> bool:
    """Return whether a session/turn pair already exists.

    Args:
        client: Connected Hebb Mind HTTP client.
        session_id: Codex session identifier.
        turn: Zero-based human turn index.

    Returns:
        ``True`` when a matching recent memory exists.
    """
    if not session_id:
        return False
    try:
        response = client.get(
            "/api/v1/memories",
            params={"partition_id": _PARTITION, "limit": _DEDUP_SCAN_LIMIT},
        )
        response.raise_for_status()
        items = response.json().get("items", [])
    except Exception:
        logger.debug("Codex duplicate-turn check failed", exc_info=True)
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("metadata"), dict)
        and item["metadata"].get("session_id") == session_id
        and item["metadata"].get("turn") == turn
        for item in items
    )
