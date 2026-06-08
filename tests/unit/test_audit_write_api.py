"""Audit lane C-write-api: write-path correctness, recall gating, migration safety.

Covers the fixes in:
    * ``hebb.server.routers.memories`` — F4 (embed_batch length mismatch),
      F6 (unknown-partition rejection), INT-5 (empty update rejection).
    * ``hebb.server.routers.search`` — recall F8 (strengthening gated on
      ``strict_recall``).
    * ``hebb.storage.migrations`` — F7 (no silent vector drop on a true
      dimension mismatch of a populated table).

Handlers are exercised directly with the shared sqlite fixtures rather than via
an HTTP client — the logic under test is in the route bodies, not the wiring.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import numpy as np
import pytest
from fastapi import HTTPException

from hebb.config.settings import Settings
from hebb.models.ingest import IngestRequest
from hebb.models.memory import MemoryCreate, MemoryQuery, MemoryUpdate, SearchResponse
from hebb.server.routers import memories as memories_router
from hebb.server.routers import search as search_router
from hebb.storage.migrations import (
    EmbeddingDimensionMismatchError,
    _ensure_vec_table,
    get_connection,
    initialize_schema,
)
from hebb.storage.partition_store import SQLitePartitionStore
from hebb.storage.sqlite_store import SQLiteMemoryStore


class _ShortEmbedder:
    """Embedder that returns FEWER vectors than inputs — the F4 failure mode."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    async def embed(self, text: str) -> list[float]:
        return [0.0] * self._dim

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Drop the last input's vector — exactly what zip() would silently hide.
        return [[0.0] * self._dim for _ in texts[:-1]]


# --------------------------------------------------------------------------- #
# F4: embed_batch returning fewer vectors than inputs must fail loud.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_batch_create_rejects_vector_count_mismatch(
    memory_store: SQLiteMemoryStore, partition_store: SQLitePartitionStore
) -> None:
    items = [
        MemoryCreate(content="alpha", partition_id="mem_hippocampus"),
        MemoryCreate(content="beta", partition_id="mem_hippocampus"),
    ]
    with pytest.raises(HTTPException) as exc:
        await memories_router.create_memories_batch(
            items=items,
            store=memory_store,
            embedder=_ShortEmbedder(),
            partitions=partition_store,
        )
    assert exc.value.status_code == 502
    # Nothing was written: the tail row is not silently inserted without a vector.
    _, total = await memory_store.list()
    assert total == 0


@pytest.mark.asyncio
async def test_ingest_rejects_vector_count_mismatch(
    memory_store: SQLiteMemoryStore, partition_store: SQLitePartitionStore
) -> None:
    req = IngestRequest(
        content="[user]: hi\n[assistant]: hello\n[user]: bye",
        format_hint="plain",
        partition_id="mem_hippocampus",
    )
    with pytest.raises(HTTPException) as exc:
        await memories_router.ingest_conversation(
            data=req,
            store=memory_store,
            embedder=_ShortEmbedder(),
            partitions=partition_store,
        )
    assert exc.value.status_code == 502
    _, total = await memory_store.list()
    assert total == 0


# --------------------------------------------------------------------------- #
# F6: writes into a non-existent partition are rejected.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_rejects_unknown_partition(
    memory_store: SQLiteMemoryStore, partition_store: SQLitePartitionStore, noop_embedder: Any
) -> None:
    with pytest.raises(HTTPException) as exc:
        await memories_router.create_memory(
            data=MemoryCreate(content="x", partition_id="does_not_exist"),
            store=memory_store,
            embedder=noop_embedder,
            partitions=partition_store,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_batch_rejects_unknown_partition(
    memory_store: SQLiteMemoryStore, partition_store: SQLitePartitionStore, noop_embedder: Any
) -> None:
    items = [
        MemoryCreate(content="ok", partition_id="mem_hippocampus"),
        MemoryCreate(content="bad", partition_id="ghost"),
    ]
    with pytest.raises(HTTPException) as exc:
        await memories_router.create_memories_batch(
            items=items,
            store=memory_store,
            embedder=noop_embedder,
            partitions=partition_store,
        )
    assert exc.value.status_code == 404
    _, total = await memory_store.list()
    assert total == 0


@pytest.mark.asyncio
async def test_ingest_rejects_unknown_partition(
    memory_store: SQLiteMemoryStore, partition_store: SQLitePartitionStore, noop_embedder: Any
) -> None:
    req = IngestRequest(content="[user]: hi", format_hint="plain", partition_id="ghost")
    with pytest.raises(HTTPException) as exc:
        await memories_router.ingest_conversation(
            data=req,
            store=memory_store,
            embedder=noop_embedder,
            partitions=partition_store,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_accepts_known_partition(
    memory_store: SQLiteMemoryStore, partition_store: SQLitePartitionStore, noop_embedder: Any
) -> None:
    mem = await memories_router.create_memory(
        data=MemoryCreate(content="hello", partition_id="mem_hippocampus"),
        store=memory_store,
        embedder=noop_embedder,
        partitions=partition_store,
    )
    assert mem.content == "hello"


# --------------------------------------------------------------------------- #
# INT-5: an explicit empty/whitespace content edit is rejected server-side.
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
async def test_update_rejects_empty_content(
    memory_store: SQLiteMemoryStore,
    partition_store: SQLitePartitionStore,
    noop_embedder: Any,
    blank: str,
) -> None:
    mem = await memory_store.create(MemoryCreate(content="original", partition_id="mem_hippocampus"))
    with pytest.raises(HTTPException) as exc:
        await memories_router.update_memory(
            memory_id=mem.id,
            data=MemoryUpdate(content=blank),
            store=memory_store,
            embedder=noop_embedder,
        )
    assert exc.value.status_code == 422
    # The original content survives — no overwrite + re-embed happened.
    again = await memory_store.get(mem.id)
    assert again is not None
    assert again.content == "original"


@pytest.mark.asyncio
async def test_update_omitted_content_is_no_change(
    memory_store: SQLiteMemoryStore, noop_embedder: Any
) -> None:
    mem = await memory_store.create(MemoryCreate(content="original", partition_id="mem_hippocampus"))
    updated = await memories_router.update_memory(
        memory_id=mem.id,
        data=MemoryUpdate(importance_score=9.0),  # content omitted -> None
        store=memory_store,
        embedder=noop_embedder,
    )
    assert updated.content == "original"
    assert updated.importance_score == 9.0


# --------------------------------------------------------------------------- #
# recall F8: access-strengthening fires only for strict_recall surfaces.
# --------------------------------------------------------------------------- #


def _settings_with_strengthening(enabled: bool = True) -> Settings:
    return Settings(recall_strengthening_enabled=enabled)


def _fake_searcher(memory_ids: list[str]) -> AsyncMock:
    searcher = AsyncMock()
    results = [
        type("R", (), {"memory": type("M", (), {"id": mid})()})() for mid in memory_ids
    ]
    searcher.search.return_value = SearchResponse.model_construct(results=results, related=[])
    return searcher


@pytest.mark.asyncio
async def test_plain_search_does_not_strengthen() -> None:
    store = AsyncMock()
    searcher = _fake_searcher(["a", "b"])
    await search_router.search_memories(
        query=MemoryQuery(query="q"),  # strict_recall defaults to False
        searcher=searcher,
        settings=_settings_with_strengthening(True),
        store=store,
    )
    store.update_access_batch.assert_not_called()


@pytest.mark.asyncio
async def test_strict_recall_search_strengthens() -> None:
    store = AsyncMock()
    searcher = _fake_searcher(["a", "b"])
    await search_router.search_memories(
        query=MemoryQuery(query="q", strict_recall=True),
        searcher=searcher,
        settings=_settings_with_strengthening(True),
        store=store,
    )
    store.update_access_batch.assert_awaited_once_with(["a", "b"])


@pytest.mark.asyncio
async def test_strict_recall_respects_master_switch() -> None:
    store = AsyncMock()
    searcher = _fake_searcher(["a"])
    await search_router.search_memories(
        query=MemoryQuery(query="q", strict_recall=True),
        searcher=searcher,
        settings=_settings_with_strengthening(False),
        store=store,
    )
    store.update_access_batch.assert_not_called()


# --------------------------------------------------------------------------- #
# F7: a true dimension mismatch on a POPULATED table must not silently drop.
# --------------------------------------------------------------------------- #


async def _populate_one_vector(conn: Any, dim: int) -> None:
    store = SQLiteMemoryStore(conn)
    await store.create(
        MemoryCreate(content="vec", partition_id="mem_hippocampus"),
        embedding=[0.1] * dim,
    )


@pytest.mark.asyncio
async def test_dimension_mismatch_raises_without_opt_in(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.delenv("HEBB_ALLOW_EMBED_DROP", raising=False)
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path)
    try:
        await initialize_schema(conn, embedding_dim=384)
        await _populate_one_vector(conn, 384)
        # Re-init at a different dimension with data present -> must refuse.
        with pytest.raises(EmbeddingDimensionMismatchError):
            await _ensure_vec_table(conn, embedding_dim=512)
        # And the existing 384-d vectors are still there (no DROP happened).
        cursor = await conn.execute("SELECT count(*) FROM memory_embeddings")
        row = await cursor.fetchone()
        assert row[0] == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_dimension_mismatch_drops_with_opt_in(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("HEBB_ALLOW_EMBED_DROP", "1")
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path)
    try:
        await initialize_schema(conn, embedding_dim=384)
        await _populate_one_vector(conn, 384)
        # Opt-in: drop + rebuild empty at the new width, no raise.
        await _ensure_vec_table(conn, embedding_dim=512)
        cursor = await conn.execute("SELECT count(*) FROM memory_embeddings")
        row = await cursor.fetchone()
        assert row[0] == 0
        # New width is in effect: a 512-d insert succeeds.
        probe = np.zeros(512, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) VALUES ('p', 'x', ?)",
            (probe,),
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_empty_table_dim_change_is_allowed(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.delenv("HEBB_ALLOW_EMBED_DROP", raising=False)
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path)
    try:
        await initialize_schema(conn, embedding_dim=384)
        # No rows inserted: a dim change is non-destructive, so it must not raise.
        await _ensure_vec_table(conn, embedding_dim=512)
        probe = np.zeros(512, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) VALUES ('p', 'x', ?)",
            (probe,),
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_first_time_creation_unaffected(tmp_path: Any) -> None:
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path)
    try:
        # Fresh DB, no prior table: must create cleanly with no raise.
        await initialize_schema(conn, embedding_dim=384)
        probe = np.zeros(384, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) VALUES ('p', 'x', ?)",
            (probe,),
        )
    finally:
        await conn.close()
