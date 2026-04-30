"""Stop hook — trigger consolidation and cleanup."""

from __future__ import annotations

import logging

from hippocampus.integrations.claude_code._client import get_client, read_hook_input
from hippocampus.integrations.claude_code.dedup import cleanup_session

logger = logging.getLogger(__name__)


def handle() -> None:
    """Trigger consolidation and clean up session state."""
    hook_input = read_hook_input()
    session_id = hook_input.get("session_id", "")

    # Trigger consolidation (fire-and-forget on timeout)
    try:
        client = get_client(timeout=30)
        client.post("/api/v1/admin/consolidate")
        client.close()
    except Exception:
        logger.debug("Consolidation trigger failed", exc_info=True)

    # Clean up dedup state for this session
    if session_id:
        cleanup_session(session_id)
