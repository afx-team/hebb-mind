"""SessionStart and UserPromptSubmit hooks — recall cross-session memories."""

from __future__ import annotations

import logging
import sys

from hebb.ingest.noise import is_greeting_only, strip_noise
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


def _is_recall_worthy(prompt: str) -> bool:
    """Activation judgment for the UserPromptSubmit recall hook.

    This is deliberately distinct from the storage judgment in
    ``transcript._is_storable_user_text``: the two hooks ask different
    questions of the same utterance. Recall only fires for a prompt that
    carries a genuine information need — long enough to be a question and
    not a pure greeting / acknowledgement. Those greetings are still kept
    by the storage path as collected feedback; here they simply earn no
    recall.
    """
    if len(prompt) < _PROMPT_MIN_LEN:
        return False
    return not is_greeting_only(prompt)


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

    A pure greeting / acknowledgement ("hi", "thanks", "好的") carries no
    query intent, so it does not trigger a recall. This is independent of
    the storage judgment in ``transcript._is_storable_user_text`` — those
    same utterances are still *stored* there as collected feedback.
    """
    hook_input = read_hook_input()
    session_id = resolve_session_id(hook_input)
    prompt = strip_noise(hook_input.get("prompt", ""))
    if not _is_recall_worthy(prompt):
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
