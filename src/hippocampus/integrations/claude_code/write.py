"""UserPromptSubmit hook — write user message to memory."""

from __future__ import annotations

import logging

from hippocampus.ingest.noise import strip_noise
from hippocampus.integrations.claude_code._client import get_client, read_hook_input
from hippocampus.integrations.claude_code.dedup import is_duplicate, record_written

logger = logging.getLogger(__name__)

_MIN_CONTENT_LENGTH = 20


def handle() -> None:
    """Read stdin, strip noise, dedup, write to hippocampus."""
    hook_input = read_hook_input()
    session_id = hook_input.get("session_id", "")
    prompt = hook_input.get("prompt", "")

    if not prompt:
        return

    # Strip system tags and noise
    cleaned = strip_noise(prompt)
    if not cleaned or len(cleaned) < _MIN_CONTENT_LENGTH:
        return

    # Deduplicate
    if is_duplicate(session_id, cleaned):
        return

    try:
        client = get_client(timeout=8)
    except Exception:
        logger.debug("Could not connect to hippocampus service", exc_info=True)
        return

    try:
        resp = client.post(
            "/api/v1/memories",
            json={
                "content": cleaned,
                "partition_id": "mem_hippocampus",
                "importance_score": 5.0,
                "tags": ["user-prompt", "hook"],
                "metadata": {"session_id": session_id},
                "source": "hook",
            },
        )
        resp.raise_for_status()
        record_written(session_id, cleaned)
    except Exception:
        logger.debug("Memory write failed", exc_info=True)
    finally:
        client.close()
