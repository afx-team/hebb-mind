"""MCP server — thin wrapper over the Hippocampus REST API.

Exposes write_memory, search_memory, and consolidate as MCP tools.
Auto-starts the Hippocampus service if not already running.

URL resolution:
  1. hippocampus.json config file (found by walking up from cwd)
  2. Default: http://localhost:8321
  3. HIPPOCAMPUS_URL env var (explicit override for remote services)
"""

from __future__ import annotations

import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "hippocampus",
    instructions=(
        "Hippocampus is a neuroscience-inspired memory system for AI agents. "
        "Use write_memory to store new information, search_memory to recall "
        "related memories, and consolidate to organize working memories into "
        "long-term partitions."
    ),
)


def _base_url() -> str:
    """Resolve the running server URL.

    1. Read host/port from hippocampus.json (found by walking up from cwd)
    2. Fall back to http://localhost:8321 if no config file found
    3. HIPPOCAMPUS_URL env var overrides both — for remote services only
    """
    # Read from config file (cwd walk-up)
    try:
        from hippocampus.config.loader import load_settings

        s = load_settings()
        host = "127.0.0.1" if s.host in ("0.0.0.0", "") else s.host
        base = f"http://{host}:{s.port}"
    except Exception:
        base = "http://localhost:8321"

    # Explicit override for non-local / remote services
    url = os.environ.get("HIPPOCAMPUS_URL")
    if url:
        return url.rstrip("/")

    return base


def _is_server_running(url: str) -> bool:
    """Check if the Hippocampus service is reachable."""
    try:
        httpx.get(f"{url}/health", timeout=3)
        return True
    except (httpx.ConnectError, httpx.RemoteProtocolError):
        return False


def _ensure_service_running() -> None:
    """Auto-start the Hippocampus service if not already running."""
    url = _base_url()

    if _is_server_running(url):
        return

    # Skip auto-start if using a remote URL (user manages that server)
    if os.environ.get("HIPPOCAMPUS_URL"):
        return

    # Start the service as a daemon
    import subprocess

    cmd = [sys.executable, "-m", "hippocampus.cli.main", "start", "-d"]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        # Fallback: try the installed binary
        try:
            subprocess.Popen(
                ["hippocampus", "start", "-d"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            return

    # Wait for the service to come up
    import time

    for _ in range(30):
        time.sleep(0.5)
        if _is_server_running(url):
            return


@mcp.tool()
async def write_memory(
    content: str,
    tags: list[str] | None = None,
    importance: float = 5.0,
) -> str:
    """Write a new memory to the hippocampus working inbox.

    The memory will be automatically consolidated into long-term partitions
    (semantic, episodic, preference, procedural) by the consolidation agent.

    Args:
        content: The memory content to store (1-10000 characters).
        tags: Optional tags for categorization (e.g. ["preference", "ui"]).
        importance: Importance score from 0.0 to 10.0 (default 5.0).
                    Higher importance = longer retention.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/api/v1/memories",
            json={
                "content": content,
                "tags": tags or [],
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
) -> str:
    """Search for related memories using hybrid retrieval.

    Combines vector similarity, keyword matching, and knowledge graph
    traversal to find the most relevant memories.

    Args:
        query: Natural language search query.
        top_k: Maximum number of results to return (1-100, default 5).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_base_url()}/api/v1/search",
            json={"query": query, "top_k": top_k},
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

    Processes unclassified memories from the hippocampus working inbox
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


def main() -> None:
    """Entry point for hippocampus-mcp console script."""
    _ensure_service_running()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()