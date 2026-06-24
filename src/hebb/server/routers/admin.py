"""Admin endpoints — manual triggers and stats."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from hebb.config.settings import Settings
from hebb.constants import PartitionType
from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.scheduler.consolidation_job import run_consolidation
from hebb.scheduler.forgetting_job import compute_expires_at, resolve_forgetting_params
from hebb.scheduler.manager import SchedulerManager
from hebb.server.consolidation_tracker import (
    get_run,
    get_run_log,
    list_runs,
)
from hebb.server.dependencies import (
    get_embedder,
    get_knowledge_graph,
    get_memory_store,
    get_partition_store,
    get_scheduler,
    get_settings,
)
from hebb.server.forgetting_tracker import record_run as record_forget_run
from hebb.storage.base import MemoryStore, PartitionStore
from hebb.storage.purge import purge_memory

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
    scheduler: SchedulerManager = Depends(get_scheduler),
) -> dict[str, Any]:
    # Optional body: {"partition_ids": [...], "keep_partition": bool}.
    # When ``partition_ids`` is given, each is consolidated in turn; with
    # ``keep_partition`` the consolidated memories stay in their source
    # partition (per-scenario benches). Empty body → default global
    # HIPPOCAMPUS→long-term consolidation (production / LoCoMo).
    body = body or {}
    partition_ids = body.get("partition_ids") or None
    keep_partition = bool(body.get("keep_partition", False))
    # Route through the scheduler's locked run_consolidation (INT-7) so a manual
    # /consolidate cannot overlap the daily cron job (concurrent consolidation
    # double-deletes / double-graphs the source memories). Lane E owns the lock
    # + public method on SchedulerManager; fall back to the direct call if it is
    # not present yet so this lane stays buildable in isolation.
    run = getattr(scheduler, "run_consolidation", None)
    if callable(run):
        results = await run(
            source_partitions=partition_ids,
            keep_partition=keep_partition,
        )
    else:
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


@router.post("/consolidate/start")
async def start_consolidation(
    body: dict[str, Any] | None = Body(default=None),
    scheduler: SchedulerManager = Depends(get_scheduler),
) -> dict[str, Any]:
    """Start consolidation asynchronously, return run_id for polling."""
    body = body or {}
    partition_ids = body.get("partition_ids") or None
    keep_partition = bool(body.get("keep_partition", False))
    run_id = await scheduler.start_consolidation_async(
        source_partitions=partition_ids,
        keep_partition=keep_partition,
    )
    return {"run_id": run_id}


@router.get("/consolidate/runs")
async def list_consolidation_runs() -> dict[str, Any]:
    """Return recent consolidation run history."""
    return {"runs": [r.to_dict() for r in list_runs()]}


@router.get("/consolidate/runs/{run_id}")
async def get_consolidation_run(run_id: str) -> dict[str, Any]:
    """Return status and summary for a single run."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.to_dict()


@router.get("/consolidate/runs/{run_id}/log")
async def get_consolidation_log(run_id: str) -> dict[str, Any]:
    """Return log content for a run."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    log = get_run_log(run_id)
    return {"run_id": run_id, "log": log or ""}


@router.post("/forget")
async def trigger_forgetting(
    memory_store: MemoryStore = Depends(get_memory_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
    settings: Settings = Depends(get_settings),
    partition_store: PartitionStore = Depends(get_partition_store),
) -> dict[str, int]:
    """Manually run the forgetting sweep.

    Mirrors the scheduled forgetting job rather than a raw ``delete_expired()``:
    each candidate's ``expires_at`` is recomputed from its *current* access state
    (access_count / last_accessed_at / importance) before the cutoff test, so a
    memory that was recently strengthened by recall is not deleted on a stale
    ``expires_at``. The HIPPOCAMPUS working-memory inbox is never swept — it is
    drained by consolidation, not by TTL — matching the scheduler.

    Args:
        memory_store: Backing memory store.
        kg: Knowledge graph kept in sync via :func:`purge_memory`.
        settings: Retention-model forgetting parameters + per-partition overrides.
        partition_store: Source of the partition list to iterate.

    Returns:
        ``{"deleted": <count>}`` — number of memories purged.
    """
    started_at = time.time()
    now = datetime.now(timezone.utc)
    deleted = 0
    scanned = 0
    partitions_swept = 0
    try:
        partitions = await partition_store.list()
        for partition in partitions:
            if partition.id == PartitionType.HIPPOCAMPUS.value:
                continue
            # Honor the per-partition forgetting policy, exactly like the scheduled
            # sweep — a disabled partition is left untouched.
            fparams = resolve_forgetting_params(partition.id, settings)
            if not fparams.enabled:
                continue
            partitions_swept += 1
            memories = await memory_store.get_by_partition(partition.id)
            scanned += len(memories)
            for memory in memories:
                # Recompute expiry from current access state so strengthened
                # (recently recalled) memories survive, then persist for visibility.
                expires_at = compute_expires_at(
                    memory,
                    half_life_days=fparams.half_life_days,
                    k_importance=fparams.k_importance,
                    k_access=fparams.k_access,
                    threshold=fparams.threshold,
                    min_retention_days=settings.forget_min_retention_days,
                )
                await memory_store.update_expiry(memory.id, expires_at.isoformat())
                if expires_at < now:
                    await purge_memory(memory_store, kg, memory.id, save=False)
                    deleted += 1
        if deleted > 0:
            kg.save()
    except Exception as exc:
        # Record the failed sweep (mirrors the scheduled job) before surfacing
        # the error, so a manual run that errors mid-way still leaves a record.
        record_forget_run(
            trigger="manual",
            started_at=started_at,
            scanned=scanned,
            deleted=deleted,
            partitions_swept=partitions_swept,
            status="failed",
            error=str(exc),
        )
        raise
    record_forget_run(
        trigger="manual",
        started_at=started_at,
        scanned=scanned,
        deleted=deleted,
        partitions_swept=partitions_swept,
    )
    return {"deleted": deleted}


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


@router.post("/shutdown")
async def shutdown_service() -> dict[str, Any]:
    """Stop the OS-managed service without restarting it.

    Used by the upgrade helper to take the daemon down while it replaces the
    package on disk (``/restart`` brings it straight back up). Returns
    immediately; the stop is dispatched ~1s later so the HTTP response flushes
    first. When no installed service is found in any scope, falls back to an
    in-process exit.
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

    async def _do_shutdown() -> None:
        await asyncio.sleep(1.0)
        for scope in ("user", "system"):
            try:
                manager = get_manager(scope=scope)
                if manager.status().installed:
                    manager.stop()
                    return
            except ServiceNotInstalledError:
                continue
            except ServiceError as exc:
                logger.error("ServiceError during shutdown (scope=%s): %s", scope, exc)
                continue
            except Exception:
                logger.exception("Unexpected error during shutdown (scope=%s)", scope)
                continue
        # No installed service to stop. Do NOT os._exit here: if this process is
        # wrapped by an external KeepAlive supervisor, exiting just triggers an
        # immediate respawn (a no-op at best, a flap loop at worst). A
        # serviceless daemon has nothing to "shut down" via this path.
        logger.warning("Shutdown requested but no installed service found; leaving process running")

    asyncio.create_task(_do_shutdown())
    return {"message": "Shutdown scheduled", "poll": "/health"}


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
