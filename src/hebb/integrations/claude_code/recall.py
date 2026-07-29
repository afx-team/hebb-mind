"""SessionStart and UserPromptSubmit hooks — recall cross-session memories."""

from __future__ import annotations

import logging
import sys
from typing import Any

import httpx

from hebb.config.loader import load_settings
from hebb.ingest.noise import is_greeting_only, strip_noise
from hebb.integrations.claude_code._client import (
    get_client,
    read_hook_input,
    resolve_session_id,
)

logger = logging.getLogger(__name__)

_TOP_K_FETCH = 20
_TOP_K_RETURN = 10
# Cap on the adaptive over-fetch: if a long active session drowns out the
# initial fetch, re-issue the search with a larger ``top_k`` until enough
# cross-session results survive the filter or this ceiling is reached. Bounded
# so a pathological session can never trigger an unbounded fetch loop.
_TOP_K_FETCH_MAX = 100
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


def _resolve_hook_min_score() -> float | None:
    """Return the per-deployment min_score override, or None for strict_recall."""
    try:
        return load_settings().recall_hook_min_score
    except Exception:
        return None


def handle() -> None:
    """SessionStart: warm up with a generic background recall."""
    hook_input = read_hook_input()
    session_id = resolve_session_id(hook_input)
    _recall_and_print(
        query=_SESSION_START_QUERY,
        current_session_id=session_id,
        timeout=20,
        min_score=_resolve_hook_min_score(),
    )


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
    _recall_and_print(
        query=prompt,
        current_session_id=session_id,
        timeout=5,
        min_score=_resolve_hook_min_score(),
    )


def _recall_and_print(query: str, current_session_id: str, timeout: float, min_score: float | None = None) -> None:
    """Shared search → filter → emit pipeline for both hooks.

    A hook must never disturb the host: every step — connecting, searching,
    and shaping the results into output — is guarded so a service outage or a
    response-shape drift degrades to a silent no-op rather than a traceback
    surfacing into Claude Code.

    Args:
        query: Search query string.
        current_session_id: Session id whose own memories are excluded from
            recall; ``""`` disables that filter.
        timeout: Per-request HTTP timeout in seconds.
    """
    try:
        client = get_client(timeout=timeout)
    except Exception:
        logger.debug("Could not connect to hebb service", exc_info=True)
        return

    try:
        results = _fetch_filtered(client, query, current_session_id, min_score=min_score)
    except Exception:
        logger.debug("Memory recall failed", exc_info=True)
        return
    finally:
        client.close()

    if not results:
        return

    try:
        _emit(results)
    except Exception:
        # Response-shape drift (a missing ``content``/``memory`` key, a
        # non-string field) must not raise out of the hook.
        logger.debug("Memory recall output failed", exc_info=True)


def _fetch_filtered(client: httpx.Client, query: str, current_session_id: str, min_score: float | None = None) -> list[dict[str, Any]]:
    """Search, then drop current-session hits, over-fetching when starved.

    Filtering the current session *after* the fetch means a long active
    session can consume most of a fixed page, leaving far fewer than
    ``_TOP_K_RETURN`` cross-session results. When that happens the search is
    re-issued with a larger ``top_k`` (doubling up to ``_TOP_K_FETCH_MAX``)
    until enough survive the filter or the service has no more to give.

    Args:
        client: An open HTTP client for the Hebb Mind REST API.
        query: Search query string.
        current_session_id: Session id to exclude; ``""`` disables the filter.

    Returns:
        Up to ``_TOP_K_RETURN`` result dicts from other sessions.

    Raises:
        Exception: Propagates any HTTP / JSON error to the caller, which logs
            it at debug and degrades to a no-op.
    """
    top_k = _TOP_K_FETCH
    while True:
        body: dict[str, object] = {"query": query, "top_k": top_k}
        if min_score is not None:
            body["min_score"] = min_score
        else:
            body["strict_recall"] = True
        resp = client.post(
            "/api/v1/search",
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", []) or []

        filtered = [r for r in results if not _is_current_session(r, current_session_id)]

        # Enough survivors, or the service returned fewer than we asked for
        # (so a bigger page can't help), or we've hit the over-fetch ceiling.
        if len(filtered) >= _TOP_K_RETURN or len(results) < top_k or top_k >= _TOP_K_FETCH_MAX:
            return filtered[:_TOP_K_RETURN]
        top_k = min(top_k * 2, _TOP_K_FETCH_MAX)


def _is_current_session(result: dict[str, Any], current_session_id: str) -> bool:
    """True when a result belongs to the session that triggered the recall."""
    if not current_session_id:
        return False
    mem = result.get("memory") or {}
    meta = mem.get("metadata") or {}
    return bool(meta.get("session_id") == current_session_id)


def _emit(results: list[dict[str, Any]]) -> None:
    """Render filtered results as a ``<cross-session-memory>`` block.

    Each result is shaped defensively: a malformed entry (no ``memory`` or no
    ``content``) is skipped rather than allowed to raise out of the hook.

    Args:
        results: Filtered search-result dicts to render.
    """
    lines: list[str] = []
    for r in results:
        mem = r.get("memory") or {}
        content = mem.get("content")
        if not content:
            continue
        score = r.get("score", 0) or 0
        partition = mem.get("partition_id", "")
        tags = mem.get("tags") or []
        tag_str = f" tags=[{', '.join(tags)}]" if tags else ""
        lines.append(f"[{partition}] (score={score:.2f}{tag_str}) {content}")

    if not lines:
        return

    output = "\n".join(lines)
    sys.stdout.write(f'<cross-session-memory source="hebb" count="{len(lines)}">\n{output}\n</cross-session-memory>\n')
