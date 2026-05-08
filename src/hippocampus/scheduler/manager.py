"""Scheduler manager — APScheduler integration for consolidation and forgetting."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from hippocampus.config.settings import Settings
from hippocampus.constants import PartitionType
from hippocampus.embedding.base import EmbeddingProvider
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.scheduler.consolidation_job import run_consolidation
from hippocampus.scheduler.forgetting_job import compute_expires_at
from hippocampus.storage.base import MemoryStore, PartitionStore

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
        self.scheduler.start()
        logger.info(
            "Scheduler started: consolidation daily at %s, forgetting every %ds",
            self.settings.consolidation_time,
            self.settings.forget_interval_seconds,
        )

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    async def _run_consolidation(self) -> None:
        logger.info("Starting consolidation job")
        try:
            await run_consolidation(
                memory_store=self.memory_store,
                partition_store=self.partition_store,
                knowledge_graph=self.knowledge_graph,
                embedder=self.embedder,
                settings=self.settings,
            )
        except Exception:
            logger.error("Consolidation job failed", exc_info=True)

    async def _run_forgetting(self) -> None:
        logger.info("Starting forgetting job")
        try:
            total_deleted = 0

            # Get all non-HIPPOCAMPUS memories
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
                    # Update the stored expires_at for visibility
                    await self.memory_store.update_expiry(memory.id, expires_at.isoformat())
                    if expires_at < now:
                        await self.memory_store.delete(memory.id)
                        self.knowledge_graph.remove_memory_from_tags(memory.id)
                        total_deleted += 1

            if total_deleted > 0:
                self.knowledge_graph.save()

            logger.info("Forgetting job complete: %d memories deleted", total_deleted)
        except Exception:
            logger.error("Forgetting job failed", exc_info=True)

    def get_status(self) -> dict:
        """Return scheduler status info."""
        jobs = {}
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
