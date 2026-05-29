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

    try:
        resp = client.post(
            "/api/v1/memories",
            json={
                "content": content,
                "partition_id": "mem_hippocampus",
                "importance_score": 4.0,
                "tags": tags,
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
