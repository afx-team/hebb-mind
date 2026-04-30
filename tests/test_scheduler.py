"""Tests for scheduler manager and jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hippocampus.embedding.local import NoopEmbedder
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.models.memory import Memory, MemoryCreate
from hippocampus.scheduler.forgetting_job import compute_expires_at
from hippocampus.scheduler.manager import SchedulerManager


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
        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_get_status(self, scheduler):
        scheduler.start()
        status = scheduler.get_status()
        assert status["running"] is True
        assert status["jobs"]["consolidation_job"]["next_run_time"] is not None
        assert status["jobs"]["forgetting_job"]["next_run_time"] is not None
        scheduler.shutdown()


class TestForgettingJob:
    def test_compute_expires_at(self):
        now = datetime.now(timezone.utc)
        mem = Memory(
            id="test",
            content="test",
            last_accessed_at=now,
            access_count=5,
            importance_score=8.0,
        )
        expires = compute_expires_at(mem, base_ttl_hours=168.0, decay_factor=0.693)
        assert expires > now

    def test_high_importance_memory_expires_later(self):
        now = datetime.now(timezone.utc)
        low = Memory(
            id="low",
            content="x",
            last_accessed_at=now,
            access_count=1,
            importance_score=2.0,
        )
        high = Memory(
            id="high",
            content="x",
            last_accessed_at=now,
            access_count=1,
            importance_score=9.0,
        )
        exp_low = compute_expires_at(low, 168.0, 0.693)
        exp_high = compute_expires_at(high, 168.0, 0.693)
        assert exp_high > exp_low

    @pytest.mark.asyncio
    async def test_forgetting_deletes_old_memories(self, memory_store, partition_store, tmp_path):
        """Memories with expired TTL should be deleted by forgetting job."""
        # Create a memory in semantic partition with very old access time
        mem = await memory_store.create(
            MemoryCreate(content="old fact", partition_id="mem_semantic"),
        )

        # Set last_accessed_at to 365 days ago and low importance
        old_time = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        await memory_store.db.execute(
            "UPDATE memories SET last_accessed_at = ?, importance_score = 1.0 WHERE id = ?",
            (old_time, mem.id),
        )
        await memory_store.db.commit()

        # Compute expiry — should be in the past
        updated_mem = await memory_store.get(mem.id)
        expires = compute_expires_at(updated_mem, base_ttl_hours=168.0, decay_factor=0.693)
        assert expires < datetime.now(timezone.utc), "Old low-importance memory should already be expired"

        # Set expires_at in DB
        await memory_store.update_expiry(mem.id, expires.isoformat())

        # Run delete_expired
        deleted_ids = await memory_store.delete_expired()
        assert len(deleted_ids) == 1
        assert mem.id in deleted_ids

        # Verify gone
        assert await memory_store.get(mem.id) is None
