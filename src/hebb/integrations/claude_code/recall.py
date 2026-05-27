"""SessionStart and UserPromptSubmit hooks — recall cross-session memories."""

from __future__ import annotations

import logging
import sys

from hebb.ingest.noise import strip_noise
from hebb.integrations.claude_code._client import (
    get_client,
    read_hook_input,
    resolve_session_id,
)

logger = logging.getLogger(__name__)

_TOP_K_FETCH = 20
_TOP_K_RETURN = 10
_PROMPT_MIN_LEN = 4
_SESSION_START_QUERY = "recent context and user preferences"


def handle() -> None:
    """SessionStart: warm up with a generic background recall."""
    hook_input = read_hook_input()
    session_id = resolve_session_id(hook_input)
    _recall_and_print(query=_SESSION_START_QUERY, current_session_id=session_id, timeout=20)


def handle_prompt() -> None:
    """UserPromptSubmit: recall memories relevant to *this* prompt.

    The user's prompt — stripped of system-reminder noise — is the search
    query. Memories from the current session are excluded so the model
    doesn't re-read what's already in its context.
    """
    hook_input = read_hook_input()
    session_id = resolve_session_id(hook_input)
    prompt = strip_noise(hook_input.get("prompt", ""))
    if len(prompt) < _PROMPT_MIN_LEN:
        return
    _recall_and_print(query=prompt, current_session_id=session_id, timeout=5)


def _recall_and_print(query: str, current_session_id: str, timeout: float) -> None:
    """Shared search → filter → emit pipeline for both hooks."""
    try:
        client = get_client(timeout=timeout)
    except Exception:
        logger.debug("Could not connect to hebb service", exc_info=True)
        return

    try:
        resp = client.post(
            "/api/v1/search",
            json={"query": query, "top_k": _TOP_K_FETCH},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.debug("Memory recall failed", exc_info=True)
        return
    finally:
        client.close()

    results = data.get("results", [])
    if not results:
        return

    filtered = []
    for r in results:
        mem = r["memory"]
        meta = mem.get("metadata", {})
        if current_session_id and meta.get("session_id") == current_session_id:
            continue
        filtered.append(r)
        if len(filtered) >= _TOP_K_RETURN:
            break

    if not filtered:
        return

    lines = []
    for r in filtered:
        mem = r["memory"]
        score = r.get("score", 0)
        partition = mem.get("partition_id", "")
        tags = mem.get("tags", [])
        content = mem["content"]

        tag_str = f" tags=[{', '.join(tags)}]" if tags else ""
        lines.append(f"[{partition}] (score={score:.2f}{tag_str}) {content}")

    output = "\n".join(lines)
    sys.stdout.write(
        f'<cross-session-memory source="hebb" count="{len(filtered)}">\n{output}\n</cross-session-memory>\n'
    )
