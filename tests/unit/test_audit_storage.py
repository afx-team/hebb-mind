"""Audit remediation tests for the SQLite store (lane D-storage).

Covers the atomicity / serialization / dim-guard / batch-expiry fixes:

- ``create`` rolls back fully on a forced FTS write error — no orphan
  ``memories`` row left behind (audit write F2).
- An embedding whose length does not match the vec0 width raises
  ``EmbeddingDimensionError`` and writes nothing (embedding F2).
- Concurrent ``create`` calls on one shared store do not interleave their
  multi-statement transactions (INT-2).
- ``update_expiry_batch`` applies all updates atomically (INT-6).
- Concurrent write + consolidation + forgetting under the shared process-level
  lock produces no orphans and no lost rows (Issue #36, C1).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import MemoryCreate
from hebb.storage.migrations import get_connection, initialize_schema
from hebb.storage.sqlite_store import EmbeddingDimensionError, SQLiteMemoryStore


@pytest.fixture
def embedding_dim() -> int:
    return 8


@pytest.fixture
async def store(tmp_path, embedding_dim: int) -> AsyncIterator[SQLiteMemoryStore]:
    db = await get_connection(str(tmp_path / "audit.db"))
    await initialize_schema(db, embedding_dim)
    yield SQLiteMemoryStore(db)
    await db.close()


async def _count_memories(store: SQLiteMemoryStore) -> int:
    cursor = await store.db.execute("SELECT count(*) FROM memories")
    row = await cursor.fetchone()
    return int(row[0]) if row is not None else 0


class TestCreateAtomicity:
    @pytest.mark.asyncio
    async def test_create_rolls_back_on_fts_error(
        self, store: SQLiteMemoryStore, monkeypatch
    ) -> None:
        """A failure on the FTS insert must roll back the memories row too."""
        real_execute = store.db.execute

        async def flaky_execute(sql: str, *args: object, **kwargs: object):
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
        assert row is not None
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


class TestConcurrentWriteConsolidateForget:
    """Concurrent write + consolidation + forgetting under the shared process-level
    write lock (Issue #36, acceptance criterion 4).

    Drives three tasks concurrently against a single SQLiteMemoryStore +
    KnowledgeGraph that share one ``asyncio.Lock``:

    * Task A — interactive API write: ``store.create()`` + KG ``update_from_tags`` + ``save``.
    * Task B — consolidation simulation: ``_create_impl`` + ``update_from_tags`` +
      ``_delete_impl`` + ``remove_memory_from_tags`` + ``save`` (all under the shared lock).
    * Task C — forgetting simulation: ``_delete_impl`` + ``remove_memory_from_tags`` +
      ``save`` (all under the shared lock).

    Asserts zero KG→SQL orphans and zero lost rows after all tasks finish.
    """

    @pytest.fixture
    async def shared_store_and_kg(
        self, tmp_path, embedding_dim: int
    ) -> AsyncIterator[tuple[SQLiteMemoryStore, KnowledgeGraph, asyncio.Lock]]:
        lock = asyncio.Lock()
        db = await get_connection(str(tmp_path / "stress.db"))
        await initialize_schema(db, embedding_dim)
        store = SQLiteMemoryStore(db, write_lock=lock)
        kg = KnowledgeGraph(tmp_path / "stress_kg.json", lock=lock)
        yield store, kg, lock
        await db.close()

    @pytest.mark.asyncio
    async def test_no_orphans_after_concurrent_operations(
        self,
        shared_store_and_kg: tuple[SQLiteMemoryStore, KnowledgeGraph, asyncio.Lock],
    ) -> None:
        store, kg, lock = shared_store_and_kg

        # Pre-populate: 10 memories with tags, half flagged for "forgetting".
        initial_ids: list[str] = []
        for i in range(10):
            async with lock:
                await store._begin()
                try:
                    m = await store._create_impl(
                        MemoryCreate(
                            partition_id="p1", content=f"seed-{i}", tags=[f"tag-{i}"]
                        ),
                        skip_tx=True,
                    )
                    await store.db.commit()
                except BaseException:
                    await store.db.rollback()
                    raise
                kg.update_from_tags([f"tag-{i}"], m.id)
                kg.save()
            initial_ids.append(m.id)

        # IDs to be "forgotten" (first 5).
        forget_ids = initial_ids[:5]

        async def api_write() -> None:
            """Simulate REST API writes interleaving with background tasks.

            Uses the composite create path (``_create_impl`` + explicit BEGIN)
            under the shared lock, with the KG mutation applied AFTER the commit
            succeeds — mirroring the production ordering the review enforced
            (Issue #36; Gemini review of in-memory graph divergence on rollback).
            """
            for i in range(10):
                async with lock:
                    await store._begin()
                    try:
                        m = await store._create_impl(
                            MemoryCreate(
                                partition_id="p1",
                                content=f"api-{i}",
                                tags=[f"api-tag-{i}"],
                            ),
                            skip_tx=True,
                        )
                        await store.db.commit()
                    except BaseException:
                        await store.db.rollback()
                        raise
                    kg.update_from_tags([f"api-tag-{i}"], m.id)
                    kg.save()

        async def consolidation_sim() -> None:
            """Simulate a consolidation step: create new + delete source in one
            SQL transaction under the shared lock, then sync the KG afterwards."""
            for i in range(5):
                source_id = initial_ids[5 + i]  # second half as consolidation sources
                async with lock:
                    await store._begin()
                    try:
                        new_mem = await store._create_impl(
                            MemoryCreate(
                                partition_id="p2",
                                content=f"consolidated-{i}",
                                tags=[f"con-tag-{i}"],
                            ),
                            skip_tx=True,
                        )
                        await store._delete_impl(source_id, skip_tx=True)
                        await store.db.commit()
                    except BaseException:
                        await store.db.rollback()
                        raise
                    kg.update_from_tags([f"con-tag-{i}"], new_mem.id)
                    kg.remove_memory_from_tags(source_id)
                    kg.save()

        async def forgetting_sim() -> None:
            """Simulate a forgetting sweep: delete expired memories in one SQL
            transaction under the shared lock, then strip KG refs afterwards."""
            async with lock:
                await store._begin()
                try:
                    for mid in forget_ids:
                        await store._delete_impl(mid, skip_tx=True)
                    await store.db.commit()
                except BaseException:
                    await store.db.rollback()
                    raise
                for mid in forget_ids:
                    kg.remove_memory_from_tags(mid)
                kg.save()

        # Run all three concurrently.
        await asyncio.gather(api_write(), consolidation_sim(), forgetting_sim())

        # 1. No KG→SQL orphan: every memory_id referenced in the KG must exist in SQL.
        referenced: set[str] = set()
        for node_id in kg.graph.nodes:
            referenced.update(kg.graph.nodes[node_id].get("memory_ids", []))
        for mid in referenced:
            assert await store.get(mid) is not None, f"KG references non-existent memory {mid} (orphan)"

        # 2. No lost rows: verify expected counts.
        #    - api_write created 10 new memories in p1.
        #    - consolidation_sim created 5 new memories in p2, deleted 5 sources from p1.
        #    - forgetting_sim deleted 5 memories from p1.
        #    Initial: 10 in p1. After: 10 (api) + 0 (5 deleted by consolidation, 5 by forget) in p1,
        #    5 in p2.
        _, p1_count = await store.list(partition_id="p1")
        _, p2_count = await store.list(partition_id="p2")
        assert p1_count == 10, f"Expected 10 in p1, got {p1_count}"
        assert p2_count == 5, f"Expected 5 in p2, got {p2_count}"

        # 3. KG file can be loaded cleanly.
        kg2 = KnowledgeGraph(kg.path)
        assert kg2.graph.number_of_nodes() > 0

    @pytest.mark.asyncio
    async def test_rollback_on_injected_failure_in_consolidation(
        self,
        shared_store_and_kg: tuple[SQLiteMemoryStore, KnowledgeGraph, asyncio.Lock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An injected SQL failure mid-consolidation must leave both the SQL store
        AND the in-memory KG unchanged — no half-applied rows, no half-stripped KG
        refs (Issue #36; Gemini review of in-memory graph divergence on rollback).

        Reproduces the exact ordering the consolidated fast-path now uses:
        ``_begin`` → ``_create_impl(skip_tx=True)`` → ``_delete_impl(skip_tx=True)`` →
        ``commit`` → KG mutations, with KG mutations running only after the commit
        succeeds. If the delete fails, ``db.rollback()`` reverts SQL and the graph
        must not have been mutated, so a reloaded graph matches the pre-failure
        snapshot exactly.
        """
        store, kg, lock = shared_store_and_kg

        # Seed one target memory (will be deleted during consolidation) tagged so
        # we can assert the tag survives the rollback.
        async with lock:
            await store._begin()
            try:
                target = await store._create_impl(
                    MemoryCreate(partition_id="p1", content="target", tags=["kept-tag"]),
                    skip_tx=True,
                )
                await store.db.commit()
            except BaseException:
                await store.db.rollback()
                raise
            kg.update_from_tags(["kept-tag"], target.id)
            kg.save()

        # Snapshot SQL row count and on-disk KG state before injection.
        rows_before = await _count_memories(store)
        kg_before_path = kg.path
        kg_before_text = kg_before_path.read_text() if kg_before_path.exists() else ""

        # Inject a failure on the second SQL call inside the consolidation path
        # (the source delete) so that the create has already executed but commit
        # never happens.
        original_delete = store._delete_impl
        delete_calls = 0

        async def flaky_delete(memory_id: str, *, skip_tx: bool = False) -> bool:
            nonlocal delete_calls
            delete_calls += 1
            if delete_calls == 1:
                raise RuntimeError("injected delete failure")
            return await original_delete(memory_id, skip_tx=skip_tx)

        monkeypatch.setattr(store, "_delete_impl", flaky_delete)

        # Drive the same critical section the production path uses. The lock is
        # acquired explicitly so the test exercises the real ordering.
        with pytest.raises(RuntimeError, match="injected delete failure"):
            async with lock:
                await store._begin()
                try:
                    await store._create_impl(
                        MemoryCreate(
                            partition_id="p2",
                            content="consolidated",
                            tags=["new-tag"],
                        ),
                        skip_tx=True,
                    )
                    # This raises — the create must NOT commit.
                    await store._delete_impl(target.id, skip_tx=True)
                    await store.db.commit()
                except BaseException:
                    await store.db.rollback()
                    raise
                # These lines must NOT execute when the delete raises.
                kg.update_from_tags(["new-tag"], "<new-id>")
                kg.remove_memory_from_tags(target.id)
                kg.save()

        # 1. SQL row count unchanged: the rollback reverted the create.
        assert await _count_memories(store) == rows_before, (
            "rollback failed: rows committed despite the injected failure"
        )
        # 2. The seeded target row still exists.
        assert await store.get(target.id) is not None, "target row was lost despite rollback"

        # 3. KG on disk unchanged: save() never ran after the commit failed.
        assert (
            kg.path.read_text() if kg.path.exists() else ""
        ) == kg_before_text, "KG was persisted despite the rollback"

        # 4. In-memory KG state unchanged: the tag still references the target.
        assert kg.get_tag("kept-tag") is not None, "KG lost the pre-failure tag"
        referenced: list[str] = []
        for node_id in kg.graph.nodes:
            referenced.extend(kg.graph.nodes[node_id].get("memory_ids", []))
        assert target.id in referenced, "KG dropped the target ref on rollback"

        # 5. Reloaded KG from disk matches the in-memory graph — divergence would
        #    not be self-healing, so the assertion catches it before the orphan
        #    can be persisted by a later save.
        reloaded = KnowledgeGraph(kg.path)
        for node_id in kg.graph.nodes:
            assert node_id in reloaded.graph.nodes, f"node {node_id} missing from reloaded KG"
            in_mem_refs = set(kg.graph.nodes[node_id].get("memory_ids", []))
            on_disk_refs = set(reloaded.graph.nodes[node_id].get("memory_ids", []))
            assert in_mem_refs == on_disk_refs, (
                f"in-memory KG diverged from on-disk KG for node {node_id}"
            )
