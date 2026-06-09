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

    @pytest.mark.asyncio
    async def test_schedule_catchup_registers_one_shot_job(self, scheduler):
        scheduler.start()
        scheduler.schedule_catchup(delay_seconds=60)
        job = scheduler.scheduler.get_job("consolidation_catchup")
        assert job is not None
        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_cron_skips_when_a_run_is_in_progress(self, scheduler, tmp_path):
        """The daily cron must not stack a second run on top of a live one."""
        from hebb.server import consolidation_tracker as tracker

        tracker._runs.clear()
        tracker._handlers.clear()
        try:
            tracker.init_tracker(tmp_path / "logs")
            live = tracker.create_run("manual")  # an in-progress run
            await scheduler._run_consolidation()  # simulate a cron tick
            # The cron tick skipped: no new run was created and the live run is
            # left untouched (still the single working state).
            runs = tracker.list_runs()
            assert len(runs) == 1
            assert runs[0].run_id == live.run_id
            assert runs[0].status == "running"
        finally:
            tracker._runs.clear()
            tracker._handlers.clear()
            tracker._logs_dir = None
