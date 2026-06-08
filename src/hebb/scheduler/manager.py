"""Scheduler manager — APScheduler integration for consolidation, forgetting, and upgrade check."""

from __future__ import annotations

import asyncio
import logging
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
from hebb.scheduler.forgetting_job import compute_expires_at
from hebb.storage.base import MemoryStore, PartitionStore
from hebb.storage.purge import purge_memory
from hebb.upgrade.checker import run_check as run_upgrade_check

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

    async def run_consolidation(
        self,
        source_partitions: list[str] | None = None,
        keep_partition: bool = False,
    ) -> list[ConsolidationResult]:
        """Run consolidation under the shared consolidation lock (INT-7).

        Serialises against the cron job so the daily sweep and an admin-
        triggered ``/consolidate`` can never overlap on the shared store +
        graph. Skips cleanly (returning ``[]``) when no ``llm_model`` is
        configured, so the out-of-the-box install does not emit a daily
        ``model=None`` traceback.

        Args:
            source_partitions: Optional explicit partitions to consolidate in
                turn (per-scenario benches); defaults to global HIPPOCAMPUS.
            keep_partition: Write consolidated memories back into their source
                partition instead of a long-term partition.

        Returns:
            One ``ConsolidationResult`` per processed (or failed) memory; ``[]``
            when consolidation is skipped because no LLM model is configured.
        """
        if not self.settings.llm_model:
            logger.info("Skipping consolidation: no llm_model configured")
            return []
        async with self._consolidation_lock:
            return await run_consolidation(
                memory_store=self.memory_store,
                partition_store=self.partition_store,
                knowledge_graph=self.knowledge_graph,
                embedder=self.embedder,
                settings=self.settings,
                source_partitions=source_partitions,
                keep_partition=keep_partition,
            )

    async def _run_consolidation(self) -> None:
        logger.info("Starting consolidation job")
        try:
            await self.run_consolidation()
        except Exception:
            logger.error("Consolidation job failed", exc_info=True)

    async def _run_forgetting(self) -> None:
        logger.info("Starting forgetting job")
        try:
            total_deleted = 0
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
                memories = await self.memory_store.get_by_partition(partition.id)
                now = datetime.now(timezone.utc)

                for memory in memories:
                    expires_at = compute_expires_at(
                        memory,
                        base_ttl_hours=self.settings.base_ttl_hours,
                        decay_factor=self.settings.decay_factor,
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
        except Exception:
            logger.error("Forgetting job failed", exc_info=True)

    async def _run_upgrade_check(self) -> None:
        """Check PyPI for a newer release. No-op when ``auto_upgrade_mode == 'off'``."""
        if self.settings.auto_upgrade_mode == "off":
            logger.debug("Skipping upgrade check (auto_upgrade_mode=off)")
            return
        if self.settings.home_dir is None:
            logger.warning("Skipping upgrade check: home_dir not resolved")
            return
        try:
            await run_upgrade_check(self.settings.home_dir)
        except Exception:
            logger.error("Upgrade check job failed", exc_info=True)

    def get_status(self) -> dict[str, Any]:
        """Return scheduler status info."""
        jobs: dict[str, Any] = {}
        for job in self.scheduler.get_jobs():
            jobs[job.id] = {
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            }
        return {
            "running": self.scheduler.running,
            "jobs": jobs,
        }

    def _parse_consolidation_time(self) -> tuple[int, int]:
        hour, minute = self.settings.consolidation_time.split(":")
        return int(hour), int(minute)
