"""Scheduler manager — APScheduler integration for consolidation, forgetting, and upgrade check."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from hebb.agents.consolidation_agent import ConsolidationResult
from hebb.config.settings import Settings
from hebb.constants import PartitionType
from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.scheduler.consolidation_job import run_consolidation
from hebb.scheduler.forgetting_job import compute_expires_at, resolve_forgetting_params
from hebb.server.consolidation_tracker import (
    HEARTBEAT_INTERVAL_SECONDS,
    create_run,
    fail_run,
    finish_run,
    get_current_run,
    get_or_create_run,
    heartbeat,
)
from hebb.server.forgetting_tracker import record_run as record_forget_run
from hebb.storage.base import MemoryStore, PartitionStore
from hebb.storage.purge import purge_memory
from hebb.upgrade import state as upgrade_state
from hebb.upgrade.checker import run_check as run_upgrade_check
from hebb.upgrade.helper import spawn_detached
from hebb.upgrade.installer import build_command
from hebb.upgrade.state import UpgradeState

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages periodic consolidation and forgetting jobs."""

    def __init__(
        self,
        settings: Settings,
        memory_store: MemoryStore,
        partition_store: PartitionStore,
        knowledge_graph: KnowledgeGraph,
        embedder: EmbeddingProvider,
    ) -> None:
        self.settings = settings
        self.memory_store = memory_store
        self.partition_store = partition_store
        self.knowledge_graph = knowledge_graph
        self.embedder = embedder
        self.scheduler = AsyncIOScheduler()
        # Single lock guarding consolidation so the cron job and the admin
        # ``/consolidate`` route can never run concurrently against the shared
        # store + graph (INT-7). Lane B routes the admin handler through
        # ``run_consolidation`` below.
        self._consolidation_lock = asyncio.Lock()

    def start(self) -> None:
        hour, minute = self._parse_consolidation_time()
        self.scheduler.add_job(
            func=self._run_consolidation,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="consolidation_job",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            func=self._run_forgetting,
            trigger=IntervalTrigger(seconds=self.settings.forget_interval_seconds),
            id="forgetting_job",
            replace_existing=True,
            max_instances=1,
        )
        # Daily PyPI upgrade check (fixed 12:00 local in v1) + one-shot 30s after boot
        self.scheduler.add_job(
            func=self._run_upgrade_check,
            trigger=CronTrigger(hour=12, minute=0),
            id="upgrade_check_job",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.add_job(
            func=self._run_upgrade_check,
            trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=30)),
            id="upgrade_check_initial",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.start()
        logger.info(
            "Scheduler started: consolidation daily at %s, forgetting every %ds, upgrade check daily at 12:00",
            self.settings.consolidation_time,
            self.settings.forget_interval_seconds,
        )

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    @asynccontextmanager
    async def _heartbeat(self, run_id: str) -> AsyncIterator[None]:
        """Keep ``run_id`` marked alive for the duration of the wrapped work.

        A run that stalls or is interrupted (network loss, system sleep, hard
        kill) without raising would otherwise sit ``running`` forever. The
        independent heartbeat task bumps ``last_heartbeat`` every
        ``HEARTBEAT_INTERVAL_SECONDS`` so the tracker can distinguish a live run
        from an abandoned one and reap the latter (see ``consolidation_tracker``).
        """
        task = asyncio.create_task(self._heartbeat_loop(run_id))
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    @staticmethod
    async def _heartbeat_loop(run_id: str) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            heartbeat(run_id)

    async def run_consolidation(
        self,
        source_partitions: list[str] | None = None,
        keep_partition: bool = False,
        trigger: str = "manual",
    ) -> list[ConsolidationResult]:
        """Run consolidation under the shared consolidation lock (INT-7).

        Serialises against the cron job so the daily sweep and an admin-
        triggered ``/consolidate`` can never overlap on the shared store +
        graph. The tracked run record is created *inside* the lock so there is
        never more than one ``running`` run for this (synchronous) path — the
        single "working" state. A heartbeat keeps the run identifiable as alive
        so an interruption is reaped instead of getting stuck. Skips cleanly
        (returning ``[]``) when no ``llm_model`` is configured, so the
        out-of-the-box install does not emit a daily ``model=None`` traceback.

        Args:
            source_partitions: Optional explicit partitions to consolidate in
                turn (per-scenario benches); defaults to global HIPPOCAMPUS.
            keep_partition: Write consolidated memories back into their source
                partition instead of a long-term partition.
            trigger: ``"manual"`` for admin/API calls, ``"scheduled"`` for cron,
                ``"catchup"`` for the boot resume of an interrupted run.

        Returns:
            One ``ConsolidationResult`` per processed (or failed) memory; ``[]``
            when consolidation is skipped because no LLM model is configured.
        """
        if not self.settings.llm_model:
            logger.info("Skipping consolidation: no llm_model configured")
            return []
        async with self._consolidation_lock:
            tracked = create_run(trigger)
            try:
                async with self._heartbeat(tracked.run_id):
                    results = await run_consolidation(
                        memory_store=self.memory_store,
                        partition_store=self.partition_store,
                        knowledge_graph=self.knowledge_graph,
                        embedder=self.embedder,
                        settings=self.settings,
                        source_partitions=source_partitions,
                        keep_partition=keep_partition,
                    )
                finish_run(tracked.run_id, results)
                return results
            except Exception as exc:
                fail_run(tracked.run_id, str(exc))
                raise

    async def start_consolidation_async(
        self,
        source_partitions: list[str] | None = None,
        keep_partition: bool = False,
    ) -> str:
        """Fire-and-forget consolidation, returns run_id for polling.

        Deduplicates against an already-live run (UI double-click, page reload,
        or a manual trigger landing on top of the daily cron): if one is in
        progress its id is returned so the console attaches to it instead of
        starting a competing run.
        """
        if not self.settings.llm_model:
            logger.info("Skipping consolidation: no llm_model configured")
            tracked = create_run("manual")
            finish_run(tracked.run_id, [])
            return tracked.run_id
        run, created = get_or_create_run("manual")
        if not created:
            return run.run_id

        async def _bg() -> None:
            try:
                # Heartbeat spans the lock wait too: a run that is queued behind
                # a long-running consolidation is still alive and must not be
                # reaped as stale while it waits its turn.
                async with self._heartbeat(run.run_id):
                    async with self._consolidation_lock:
                        results = await run_consolidation(
                            memory_store=self.memory_store,
                            partition_store=self.partition_store,
                            knowledge_graph=self.knowledge_graph,
                            embedder=self.embedder,
                            settings=self.settings,
                            source_partitions=source_partitions,
                            keep_partition=keep_partition,
                        )
                finish_run(run.run_id, results)
            except Exception as exc:
                fail_run(run.run_id, str(exc))
                logger.error("Background consolidation failed", exc_info=True)

        asyncio.create_task(_bg())
        return run.run_id

    def schedule_catchup(self, delay_seconds: float = 60.0) -> None:
        """Schedule a one-shot consolidation to resume after an interrupted run.

        Called at startup when the tracker reaped a run that did not finish
        (system stopped/slept/lost network mid-consolidation). Because the
        consolidation batch drains the working inbox, simply re-running it
        processes whatever the interrupted run left behind — "下次继续". A short
        delay lets the service finish coming up (and a transient outage settle)
        first; if it still fails, the daily cron remains the backstop.
        """
        self.scheduler.add_job(
            func=self._run_catchup,
            trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=delay_seconds)),
            id="consolidation_catchup",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            "Scheduled consolidation catch-up in %ds to resume an interrupted run",
            int(delay_seconds),
        )

    async def _run_catchup(self) -> None:
        if get_current_run() is not None:
            logger.info("Consolidation already running; catch-up not needed")
            return
        logger.info("Running consolidation catch-up to resume interrupted run")
        try:
            await self.run_consolidation(trigger="catchup")
        except Exception:
            logger.error("Catch-up consolidation failed", exc_info=True)

    async def _run_consolidation(self) -> None:
        # Skip this scheduled tick if a run is already in progress so the cron
        # never stacks a second run on top of a long manual/catch-up run.
        if get_current_run() is not None:
            logger.info("Consolidation already in progress; skipping scheduled tick")
            return
        logger.info("Starting consolidation job")
        try:
            await self.run_consolidation(trigger="scheduled")
        except Exception:
            logger.error("Consolidation job failed", exc_info=True)

    async def _run_forgetting(self) -> None:
        logger.info("Starting forgetting job")
        started_at = time.time()
        scanned = 0
        partitions_swept = 0
        total_deleted = 0
        try:
            # Accumulate expiry refreshes and deletions across all partitions so
            # we persist them in batches instead of one commit per memory
            # (INT-6 / forgetting F5). Per-memory commits blocked the shared
            # connection O(N) on large corpora.
            expiry_updates: dict[str, str] = {}
            to_delete: list[str] = []

            partitions = await self.partition_store.list()
            for partition in partitions:
                if partition.id == PartitionType.HIPPOCAMPUS.value:
                    continue
                # Per-partition forgetting policy (config-driven); a disabled
                # partition is skipped entirely, and the retention params come from
                # its override or fall back to the region/global defaults.
                fparams = resolve_forgetting_params(partition.id, self.settings)
                if not fparams.enabled:
                    continue
                partitions_swept += 1
                memories = await self.memory_store.get_by_partition(partition.id)
                scanned += len(memories)
                now = datetime.now(timezone.utc)

                for memory in memories:
                    expires_at = compute_expires_at(
                        memory,
                        half_life_days=fparams.half_life_days,
                        k_importance=fparams.k_importance,
                        k_access=fparams.k_access,
                        threshold=fparams.threshold,
                        min_retention_days=self.settings.forget_min_retention_days,
                    )
                    iso = expires_at.isoformat()
                    # Only persist expires_at when it materially changed —
                    # avoids rewriting every row every sweep "for visibility".
                    if memory.expires_at is None or memory.expires_at.isoformat() != iso:
                        expiry_updates[memory.id] = iso
                    if expires_at < now:
                        to_delete.append(memory.id)
                        # Don't also rewrite expiry for a row we're deleting.
                        expiry_updates.pop(memory.id, None)

            # Batch-persist refreshed expiries in one transaction (INT-6) rather
            # than one commit per memory. ``update_expiry_batch`` takes
            # ``(memory_id, expires_at_iso)`` pairs; fall back to per-row
            # ``update_expiry`` if a store predates the batch API.
            if expiry_updates:
                items = list(expiry_updates.items())
                batch = getattr(self.memory_store, "update_expiry_batch", None)
                if callable(batch):
                    await batch(items)
                else:
                    for mid, iso in items:
                        await self.memory_store.update_expiry(mid, iso)

            # Batch-delete expired memories, then strip them from the graph and
            # persist the graph once — all under the graph's shared lock so a
            # concurrent consolidation can't interleave a save (C1).
            if to_delete:
                async with self.knowledge_graph.lock:
                    for mid in to_delete:
                        # save=False: the graph is persisted once after the loop.
                        await purge_memory(self.memory_store, self.knowledge_graph, mid, save=False)
                        total_deleted += 1
                    self.knowledge_graph.save()

            logger.info("Forgetting job complete: %d memories deleted", total_deleted)
            record_forget_run(
                trigger="scheduled",
                started_at=started_at,
                scanned=scanned,
                deleted=total_deleted,
                partitions_swept=partitions_swept,
            )
        except Exception as exc:
            logger.error("Forgetting job failed", exc_info=True)
            record_forget_run(
                trigger="scheduled",
                started_at=started_at,
                scanned=scanned,
                deleted=total_deleted,
                partitions_swept=partitions_swept,
                status="failed",
                error=str(exc),
            )

    async def _run_upgrade_check(self) -> None:
        """Check PyPI for a newer release. No-op when ``auto_upgrade_mode == 'off'``.

        When ``auto_upgrade_mode == 'auto'`` and a newer auto-upgradable release
        exists, spawns the upgrade helper directly (same path as ``/apply``).
        Also clears a stuck ``upgrade_in_progress`` flag left by a helper that
        died before it could report.
        """
        if self.settings.auto_upgrade_mode == "off":
            logger.debug("Skipping upgrade check (auto_upgrade_mode=off)")
            return
        if self.settings.home_dir is None:
            logger.warning("Skipping upgrade check: home_dir not resolved")
            return
        upgrade_state.reconcile_stale(self.settings.home_dir)
        try:
            state = await run_upgrade_check(self.settings.home_dir)
        except Exception:
            logger.error("Upgrade check job failed", exc_info=True)
            return
        if self.settings.auto_upgrade_mode == "auto":
            self._maybe_auto_upgrade(state)

    def _maybe_auto_upgrade(self, state: UpgradeState) -> None:
        """Trigger the upgrade helper for ``auto`` mode when one is available."""
        if self.settings.home_dir is None:
            return
        if not state.available or state.upgrade_in_progress:
            return
        cmd = build_command()
        if not cmd.auto_upgradable:
            logger.info("Auto-upgrade unavailable (%s): %s", cmd.method, cmd.refusal_reason)
            return
        try:
            pid = spawn_detached(
                home_dir=self.settings.home_dir,
                port=self.settings.port,
                grace=self.settings.upgrade_grace_seconds,
                method=cmd.method,
                parent_pid=os.getpid(),
            )
            upgrade_state.update(self.settings.home_dir, upgrade_in_progress=True, upgrade_helper_pid=pid)
            logger.info("Auto-upgrade: spawned helper to upgrade to %s", state.latest_version)
        except Exception:
            logger.exception("Auto-upgrade: failed to spawn helper")

    def get_status(self) -> dict[str, Any]:
        """Return scheduler status info."""
        jobs: dict[str, Any] = {}
        for job in self.scheduler.get_jobs():
            jobs[job.id] = {
                "next_run_time": (job.next_run_time.isoformat() if job.next_run_time else None),
            }
        return {
            "running": self.scheduler.running,
            "jobs": jobs,
        }

    def _parse_consolidation_time(self) -> tuple[int, int]:
        hour, minute = self.settings.consolidation_time.split(":")
        return int(hour), int(minute)
