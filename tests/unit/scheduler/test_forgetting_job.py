"""Tests for the forgetting job: expiry computation and expired-memory deletion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hebb.models.memory import Memory, MemoryCreate
from hebb.scheduler.forgetting_job import compute_expires_at

# A representative parameter set (the global user-partition defaults).
_PARAMS = dict(half_life_days=60.0, k_importance=2.0, k_access=1.5, threshold=0.3)


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
        expires = compute_expires_at(mem, **_PARAMS)
        assert expires > now

    def test_high_importance_memory_expires_later(self):
        now = datetime.now(timezone.utc)
        low = Memory(id="low", content="x", last_accessed_at=now, access_count=1, importance_score=2.0)
        high = Memory(id="high", content="x", last_accessed_at=now, access_count=1, importance_score=9.0)
        assert compute_expires_at(high, **_PARAMS) > compute_expires_at(low, **_PARAMS)

    def test_more_access_expires_later(self):
        now = datetime.now(timezone.utc)
        few = Memory(id="few", content="x", last_accessed_at=now, access_count=1, importance_score=5.0)
        many = Memory(id="many", content="x", last_accessed_at=now, access_count=100, importance_score=5.0)
        assert compute_expires_at(many, **_PARAMS) > compute_expires_at(few, **_PARAMS)

    @pytest.mark.asyncio
    async def test_forgetting_deletes_old_memories(self, memory_store, partition_store, tmp_path):
        """A long-idle, low-value memory should be past its retention and deleted."""
        mem = await memory_store.create(
            MemoryCreate(content="old fact", partition_id="mem_semantic"),
        )

        # Idle for 365 days, low importance, accessed a few times. With a 30-day
        # half-life and threshold 0.3 the retained lifetime is well under a year,
        # so this memory is already expired.
        old_time = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        await memory_store.db.execute(
            "UPDATE memories SET last_accessed_at = ?, created_at = ?, "
            "importance_score = 1.0, access_count = 3 WHERE id = ?",
            (old_time, old_time, mem.id),
        )
        await memory_store.db.commit()

        updated_mem = await memory_store.get(mem.id)
        expires = compute_expires_at(
            updated_mem, half_life_days=30.0, k_importance=1.0, k_access=1.0, threshold=0.3
        )
        assert expires < datetime.now(timezone.utc), "Old low-value memory should already be expired"

        await memory_store.update_expiry(mem.id, expires.isoformat())

        deleted_ids = await memory_store.delete_expired()
        assert len(deleted_ids) == 1
        assert mem.id in deleted_ids
        assert await memory_store.get(mem.id) is None
