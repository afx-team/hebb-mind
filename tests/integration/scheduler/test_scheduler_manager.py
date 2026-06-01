"""Tests for the APScheduler-backed SchedulerManager (starts a real in-process scheduler)."""

from __future__ import annotations

import pytest
from apscheduler.triggers.cron import CronTrigger

from hebb.embedding.local import NoopEmbedder
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.scheduler.manager import SchedulerManager


class TestSchedulerManager:
    @pytest.fixture
    def scheduler(self, settings, memory_store, partition_store, tmp_path):
        kg = KnowledgeGraph(tmp_path / "kg.json")
        embedder = NoopEmbedder(384)
        return SchedulerManager(
            settings=settings,
            memory_store=memory_store,
            partition_store=partition_store,
            knowledge_graph=kg,
            embedder=embedder,
        )

    @pytest.mark.asyncio
    async def test_start_and_shutdown(self, scheduler):
        scheduler.start()
        status = scheduler.get_status()
        assert status["running"] is True
        assert "consolidation_job" in status["jobs"]
        assert "forgetting_job" in status["jobs"]
        assert isinstance(scheduler.scheduler.get_job("consolidation_job").trigger, CronTrigger)
        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_get_status(self, scheduler):
        scheduler.start()
        status = scheduler.get_status()
        assert status["running"] is True
        assert status["jobs"]["consolidation_job"]["next_run_time"] is not None
        assert status["jobs"]["forgetting_job"]["next_run_time"] is not None
        scheduler.shutdown()
