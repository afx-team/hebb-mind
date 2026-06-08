"""Audit remediation tests for the SQLite store (lane D-storage).

Covers the atomicity / serialization / dim-guard / batch-expiry fixes:

- ``create`` rolls back fully on a forced FTS write error — no orphan
  ``memories`` row left behind (audit write F2).
- An embedding whose length does not match the vec0 width raises
  ``EmbeddingDimensionError`` and writes nothing (embedding F2).
- Concurrent ``create`` calls on one shared store do not interleave their
  multi-statement transactions (INT-2).
- ``update_expiry_batch`` applies all updates atomically (INT-6).
"""

from __future__ import annotations

import asyncio

import pytest

from hebb.models.memory import MemoryCreate
from hebb.storage.migrations import get_connection, initialize_schema
from hebb.storage.sqlite_store import EmbeddingDimensionError, SQLiteMemoryStore


@pytest.fixture
def embedding_dim() -> int:
    return 8


@pytest.fixture
async def store(tmp_path, embedding_dim: int) -> SQLiteMemoryStore:
    db = await get_connection(str(tmp_path / "audit.db"))
    await initialize_schema(db, embedding_dim)
    yield SQLiteMemoryStore(db)
    await db.close()


async def _count_memories(store: SQLiteMemoryStore) -> int:
    cursor = await store.db.execute("SELECT count(*) FROM memories")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


class TestCreateAtomicity:
    @pytest.mark.asyncio
    async def test_create_rolls_back_on_fts_error(
        self, store: SQLiteMemoryStore, monkeypatch
    ) -> None:
        """A failure on the FTS insert must roll back the memories row too."""
        real_execute = store.db.execute

        async def flaky_execute(sql, *args, **kwargs):  # type: ignore[no-untyped-def]
            if "memory_fts" in sql and sql.strip().upper().startswith("INSERT"):
                raise RuntimeError("forced FTS failure")
            return await real_execute(sql, *args, **kwargs)

        monkeypatch.setattr(store.db, "execute", flaky_execute)

        with pytest.raises(RuntimeError, match="forced FTS failure"):
            await store.create(MemoryCreate(partition_id="p1", content="hello world"))

        # Restore the real execute so the assertion query runs cleanly.
        monkeypatch.undo()
        assert await _count_memories(store) == 0, "orphan memories row survived the rollback"

    @pytest.mark.asyncio
    async def test_dim_mismatch_raises_and_writes_nothing(
        self, store: SQLiteMemoryStore, embedding_dim: int
    ) -> None:
        bad_embedding = [0.1] * (embedding_dim + 1)
        with pytest.raises(EmbeddingDimensionError):
            await store.create(
                MemoryCreate(partition_id="p1", content="dim mismatch"),
                embedding=bad_embedding,
            )
        assert await _count_memories(store) == 0

    @pytest.mark.asyncio
    async def test_create_with_correct_dim_succeeds(
        self, store: SQLiteMemoryStore, embedding_dim: int
    ) -> None:
        mem = await store.create(
            MemoryCreate(partition_id="p1", content="good vector"),
            embedding=[0.0] * embedding_dim,
        )
        assert mem.content == "good vector"
        assert await _count_memories(store) == 1

    @pytest.mark.asyncio
    async def test_concurrent_creates_do_not_interleave(
        self, store: SQLiteMemoryStore
    ) -> None:
        """All concurrent creates commit cleanly — none lost, none orphaned."""
        n = 25
        results = await asyncio.gather(
            *(
                store.create(MemoryCreate(partition_id="p1", content=f"mem-{i}"))
                for i in range(n)
            )
        )
        assert len({m.id for m in results}) == n
        assert await _count_memories(store) == n
        # FTS index stayed in lockstep with the base table.
        cursor = await store.db.execute("SELECT count(*) FROM memory_fts")
        row = await cursor.fetchone()
        assert int(row[0]) == n


class TestUpdateExpiryBatch:
    @pytest.mark.asyncio
    async def test_batch_sets_all_expiries(self, store: SQLiteMemoryStore) -> None:
        m1 = await store.create(MemoryCreate(partition_id="p1", content="a"))
        m2 = await store.create(MemoryCreate(partition_id="p1", content="b"))

        ts1 = "2030-01-01T00:00:00+00:00"
        ts2 = "2031-01-01T00:00:00+00:00"
        await store.update_expiry_batch([(m1.id, ts1), (m2.id, ts2)])

        cursor = await store.db.execute(
            "SELECT id, expires_at FROM memories ORDER BY content"
        )
        rows = {row["id"]: row["expires_at"] for row in await cursor.fetchall()}
        assert rows[m1.id] == ts1
        assert rows[m2.id] == ts2

    @pytest.mark.asyncio
    async def test_empty_batch_is_noop(self, store: SQLiteMemoryStore) -> None:
        await store.update_expiry_batch([])  # must not raise
