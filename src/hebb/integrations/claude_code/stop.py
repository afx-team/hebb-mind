"""Stop hook — record turn summary and cleanup."""

from __future__ import annotations

import logging

from hebb.integrations.claude_code._client import get_client, read_hook_input
from hebb.integrations.claude_code.dedup import cleanup_session
from hebb.integrations.claude_code.transcript import (
    extract_last_turn,
    format_turn_memory,
)

logger = logging.getLogger(__name__)


def handle() -> None:
    """Record the last turn and clean up session state.

    Consolidation is NOT triggered here — it runs on its own schedule
    via ``consolidation_time`` in the server lifecycle.
    """
    hook_input = read_hook_input()
    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")

    # 1. Record last turn summary as a memory.
    if transcript_path:
        try:
            client = get_client(timeout=30)
        except Exception:
            logger.debug("Could not connect to hebb service", exc_info=True)
            if session_id:
                cleanup_session(session_id)
            return

        try:
            _record_turn(client, transcript_path, session_id)
        finally:
            client.close()

    # 2. Clean up dedup state for this session.
    if session_id:
        cleanup_session(session_id)


def _record_turn(client, transcript_path: str, session_id: str) -> None:
    """Extract last turn from transcript and write it as a memory."""
    try:
        summary = extract_last_turn(transcript_path)
    except Exception:
        logger.debug("Transcript parsing failed", exc_info=True)
        return

    if summary is None:
        return

    # Skip trivial turns (no meaningful user input or assistant output).
    if not summary.user_input and not summary.assistant_output:
        return

    content = format_turn_memory(summary, session_id=session_id)
    if not content:
        return

    try:
        resp = client.post(
            "/api/v1/memories",
            json={
                "content": content,
                "partition_id": "mem_hippocampus",
                "importance_score": 4.0,
                "tags": ["turn-summary", "hook"],
                "metadata": {
                    "session_id": session_id,
                    "tools": summary.tools,
                    "mcps": summary.mcps,
                },
                "source": "hook:stop",
            },
        )
        resp.raise_for_status()
        logger.debug("Turn summary recorded")
    except Exception:
        logger.debug("Turn summary write failed", exc_info=True)
