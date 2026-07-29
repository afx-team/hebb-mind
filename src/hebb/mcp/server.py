"""MCP server — thin wrapper over the Hebb Mind REST API.

Exposes write_memory, search_memory, and consolidate as MCP tools.
Auto-starts the Hebb Mind service if not already running.

URL resolution:
  1. hebb.json config file (found by walking up from cwd)
  2. Default: http://localhost:8321
  3. HEBB_URL env var (explicit override for remote services)
"""

from __future__ import annotations

# --- Stdio protection: MUST run before any third-party imports ---
from hebb.utils.stdio_guard import capture_stdout, restore_stdout

capture_stdout()
# -----------------------------------------------------------------

import httpx  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

from hebb.integrations._project import detect_project_name  # noqa: E402
from hebb.utils.service import ensure_service_running, resolve_base_url  # noqa: E402

mcp = FastMCP(
    "hebb",
    instructions=(
        "Hebb Mind is a neuroscience-inspired memory system for AI agents. "
        "Use write_memory to store new information, search_memory to recall "
        "related memories, and consolidate to organize working memories into "
        "long-term partitions."
    ),
)


def _base_url() -> str:
    """Resolve the running server URL — delegates to shared utility."""
    return resolve_base_url()


def _is_server_running(url: str) -> bool:
    """Check if the Hebb Mind service is reachable."""
    from hebb.utils.service import is_server_running

    return is_server_running(url)


def _ensure_service_running() -> None:
    """Auto-start the Hebb Mind service if not already running."""
    ensure_service_running()


@mcp.tool()
async def write_memory(
    content: str,
    tags: list[str] | None = None,
    importance: float = 5.0,
) -> str:
    """Write a new memory to the hebb working inbox.

    The memory will be automatically consolidated into long-term partitions
    (semantic, episodic, preference, procedural) by the consolidation agent.

    Args:
        content: The memory content to store (1-10000 characters).
        tags: Optional tags for categorization (e.g. ["preference", "ui"]).
        importance: Importance score from 0.0 to 10.0 (default 5.0).
                    Higher importance = longer retention.
    """
    merged_tags = list(tags or [])
    project = detect_project_name()
    if project and project not in merged_tags:
        merged_tags.append(project)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/api/v1/memories",
            json={
                "content": content,
                "tags": merged_tags,
                "importance_score": importance,
                "partition_id": "mem_hippocampus",
            },
        )
        resp.raise_for_status()
        mem = resp.json()
    return f"Memory saved (id={mem['id']}, partition=mem_hippocampus)"


@mcp.tool()
async def search_memory(
    query: str,
    top_k: int = 5,
    min_score: float | None = None,
) -> str:
    """Search for related memories using hybrid retrieval.

    Combines vector similarity, keyword matching, and knowledge graph
    traversal to find the most relevant memories.

    Args:
        query: Natural language search query.
        top_k: Maximum number of results to return (1-100, default 5).
        min_score: Optional relevance floor (0-1). When set, overrides the
            server's configured ``recall_min_score``. When omitted, strict
            recall is enabled at the server's configured floor.
    """
    from hebb.retrieval.query_sanitizer import sanitize_query

    query = sanitize_query(query)

    body: dict[str, object] = {"query": query, "top_k": top_k}
    if min_score is not None:
        body["min_score"] = min_score
    else:
        body["strict_recall"] = True

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/api/v1/search",
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return "No memories found."

    lines = []
    for r in results:
        m = r["memory"]
        tags_str = ", ".join(m.get("tags", [])) if m.get("tags") else ""
        header = f"[{m['partition_id']}] score={r['score']:.2f}"
        if tags_str:
            header += f" tags=[{tags_str}]"
        lines.append(f"{header}\n{m['content']}")

    output = f"Found {len(results)} memories:\n\n" + "\n\n---\n\n".join(lines)

    # Append related memories from graph expansion
    related = data.get("related", [])
    if related:
        output += f"\n\n--- Related ({len(related)} via knowledge graph) ---\n\n"
        for m in related[:3]:
            output += f"[{m['partition_id']}] {m['content'][:200]}\n\n"

    return output


@mcp.tool()
async def consolidate() -> str:
    """Trigger memory consolidation.

    Processes unclassified memories from the hebb working inbox
    and organizes them into long-term partitions (semantic, episodic,
    preference, procedural). Also extracts tags for the knowledge graph.
    """
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{_base_url()}/api/v1/admin/consolidate")
        resp.raise_for_status()
        data = resp.json()

    processed = data.get("processed", 0)
    succeeded = data.get("succeeded", 0)
    failed = data.get("failed", 0)
    return f"Consolidation complete: {processed} processed, {succeeded} succeeded, {failed} failed"


@mcp.tool()
async def ingest_conversation(
    content: str,
    format_hint: str | None = None,
    importance: float = 5.0,
) -> str:
    """Ingest a conversation export into hebb memory.

    Auto-detects Claude Code JSONL, ChatGPT JSON, and plain text formats.
    Normalizes turns, strips noise, and stores each turn as a memory.

    Args:
        content: Raw conversation data (JSONL, JSON, or plain text).
        format_hint: Optional format override ('claude_code', 'chatgpt', 'plain').
        importance: Importance score from 0.0 to 10.0 (default 5.0).
    """
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{_base_url()}/api/v1/ingest",
            json={
                "content": content,
                "format_hint": format_hint,
                "partition_id": "mem_hippocampus",
                "importance_score": importance,
                "source": "mcp",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return (
        f"Ingested {data['memories_created']} memories (format={data['format_detected']}, turns={data['turns_parsed']})"
    )


def main() -> None:
    """Entry point for hebb-mcp console script."""
    restore_stdout()
    _ensure_service_running()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
