"""Admin endpoints — manual triggers and stats."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from hebb.config.settings import Settings
from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.scheduler.consolidation_job import run_consolidation
from hebb.scheduler.manager import SchedulerManager
from hebb.server.dependencies import (
    get_embedder,
    get_knowledge_graph,
    get_memory_store,
    get_partition_store,
    get_scheduler,
    get_settings,
)
from hebb.storage.base import MemoryStore, PartitionStore

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/consolidate")
async def trigger_consolidation(
    body: dict[str, Any] | None = Body(default=None),
    memory_store: MemoryStore = Depends(get_memory_store),
    partition_store: PartitionStore = Depends(get_partition_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
    embedder: EmbeddingProvider = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    # Optional body: {"partition_ids": [...], "keep_partition": bool}.
    # When ``partition_ids`` is given, each is consolidated in turn; with
    # ``keep_partition`` the consolidated memories stay in their source
    # partition (per-scenario benches). Empty body → default global
    # HIPPOCAMPUS→long-term consolidation (production / LoCoMo).
    body = body or {}
    partition_ids = body.get("partition_ids") or None
    keep_partition = bool(body.get("keep_partition", False))
    results = await run_consolidation(
        memory_store=memory_store,
        partition_store=partition_store,
        knowledge_graph=kg,
        embedder=embedder,
        settings=settings,
        source_partitions=partition_ids,
        keep_partition=keep_partition,
    )
    failures = [
        {"memory_id": r.original_memory_id, "error": r.error or "unknown error"} for r in results if not r.success
    ]
    return {
        "processed": len(results),
        "succeeded": sum(1 for r in results if r.success),
        "failed": len(failures),
        "errors": failures,
    }


@router.post("/forget")
async def trigger_forgetting(
    memory_store: MemoryStore = Depends(get_memory_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
) -> dict[str, int]:
    deleted_ids = await memory_store.delete_expired()
    for mid in deleted_ids:
        kg.remove_memory_from_tags(mid)
    if deleted_ids:
        kg.save()
    return {"deleted": len(deleted_ids)}


@router.post("/restart")
async def restart_service() -> dict[str, Any]:
    """Restart the OS-managed Hebb Mind service.

    Returns immediately; the actual restart is dispatched ~1s later so the HTTP
    response can flush before launchd / systemd / Task Scheduler stops this
    process. The client should then poll ``GET /health`` until the new process
    answers.
    """
    from hebb.utils.service_manager import (
        ServiceError,
        ServiceNotInstalledError,
        UnsupportedPlatformError,
        get_manager,
    )

    try:
        get_manager(scope="user")
    except UnsupportedPlatformError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    async def _do_restart() -> None:
        await asyncio.sleep(1.0)
        last_err: Exception | None = None
        for scope in ("user", "system"):
            try:
                manager = get_manager(scope=scope)
                manager.restart()
                return
            except ServiceNotInstalledError as exc:
                last_err = exc
                continue
            except ServiceError as exc:
                last_err = exc
                logger.error("ServiceError during restart (scope=%s): %s", scope, exc)
                continue
            except Exception as exc:
                last_err = exc
                logger.exception("Unexpected error during restart (scope=%s)", scope)
                continue
        logger.error(
            "Restart failed in every scope. Last error: %s. Falling back to in-process exit so the supervisor restarts us.",
            last_err,
        )
        # Last-ditch fallback: exit. If we're running under launchd/systemd/Task
        # Scheduler with KeepAlive, the supervisor will respawn us.
        import os

        os._exit(0)

    asyncio.create_task(_do_restart())
    return {
        "message": "Restart scheduled",
        "expected_downtime_seconds": 5,
        "poll": "/health",
    }


@router.get("/stats")
async def get_stats(
    memory_store: MemoryStore = Depends(get_memory_store),
    partition_store: PartitionStore = Depends(get_partition_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
    scheduler: SchedulerManager = Depends(get_scheduler),
) -> dict[str, Any]:
    partitions = await partition_store.list()
    partition_stats = [
        {"id": p.id, "name": p.name, "memory_count": p.memory_count, "enabled": p.enabled} for p in partitions
    ]
    graph_state = kg.export()
    return {
        "partitions": partition_stats,
        "total_memories": sum(p.memory_count for p in partitions),
        "graph": {
            "tag_count": len(graph_state.nodes),
            "edge_count": len(graph_state.edges),
        },
        "scheduler": scheduler.get_status(),
    }
