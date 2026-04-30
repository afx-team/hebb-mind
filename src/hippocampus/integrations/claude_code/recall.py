"""SessionStart hook — recall cross-session memories."""

from __future__ import annotations

import logging
import sys

from hippocampus.integrations.claude_code._client import get_client, read_hook_input

logger = logging.getLogger(__name__)

_TOP_K_FETCH = 20
_TOP_K_RETURN = 10


def handle() -> None:
    """Read stdin, search memories, filter current session, output to stdout."""
    hook_input = read_hook_input()
    session_id = hook_input.get("session_id", "")

    try:
        client = get_client(timeout=20)
    except Exception:
        logger.debug("Could not connect to hippocampus service", exc_info=True)
        return

    try:
        resp = client.post(
            "/api/v1/search",
            json={"query": "recent context and user preferences", "top_k": _TOP_K_FETCH},
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

    # Filter out current session memories (they're already in context)
    filtered = []
    for r in results:
        mem = r["memory"]
        meta = mem.get("metadata", {})
        if meta.get("session_id") == session_id:
            continue
        filtered.append(r)
        if len(filtered) >= _TOP_K_RETURN:
            break

    if not filtered:
        return

    # Format output for Claude Code context injection
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
        f'<cross-session-memory source="hippocampus" count="{len(filtered)}">\n{output}\n</cross-session-memory>\n'
    )
