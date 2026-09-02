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
    EmbeddingSchemaMigrationError,
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
async def test_update_omitted_content_is_no_change(memory_store: SQLiteMemoryStore, noop_embedder: Any) -> None:
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
    results = [type("R", (), {"memory": type("M", (), {"id": mid})()})() for mid in memory_ids]
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


@pytest.mark.asyncio
async def test_same_dim_reinit_preserves_embeddings(tmp_path: Any) -> None:
    """Re-initializing at the SAME dim must not drop existing embeddings.

    Invariant guard for the vec0-unavailable fallback path: the BLOB fallback
    table must survive a same-dim re-init (e.g. a service restart). The second
    connection also has extension loading disabled, so this exercises the real
    fallback path rather than relying on host-specific sqlite-vec behavior.
    """
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await initialize_schema(conn, embedding_dim=384)
        schema_cursor = await conn.execute("SELECT sql FROM sqlite_master WHERE name = 'memory_embeddings'")
        schema_row = await schema_cursor.fetchone()
        assert schema_row is not None
        assert "USING vec0" not in schema_row[0]

        await _populate_one_vector(conn, 384)
        assert await _vec_row_count_proxy(conn) == 1
    finally:
        await conn.close()

    # Simulate a service restart on another connection where vec0 is still
    # unavailable: initialization must reuse the populated BLOB fallback.
    conn = await get_connection(db_path, load_vec=False)
    try:
        await initialize_schema(conn, embedding_dim=384)
        assert await _vec_row_count_proxy(conn) == 1, "same-dim re-init wiped existing embeddings on the fallback path"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_populated_legacy_fallback_adds_partition_without_data_loss(tmp_path: Any) -> None:
    """Fallback schema migration is additive even when vec0 is unavailable."""
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await conn.execute("CREATE TABLE memory_embeddings (memory_id TEXT PRIMARY KEY, embedding BLOB)")
        embedding = np.zeros(384, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, embedding) VALUES ('legacy', ?)",
            (embedding,),
        )
        await conn.commit()

        await initialize_schema(conn, embedding_dim=384)

        assert await _vec_row_count_proxy(conn) == 1
        info_cursor = await conn.execute("PRAGMA table_info(memory_embeddings)")
        columns = {row[1] for row in await info_cursor.fetchall()}
        assert "partition_id" in columns
        row_cursor = await conn.execute("SELECT memory_id, partition_id, embedding FROM memory_embeddings")
        row = await row_cursor.fetchone()
        assert tuple(row) == ("legacy", "default", embedding)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_populated_legacy_fallback_infers_dimension_before_writing_meta(tmp_path: Any, monkeypatch: Any) -> None:
    """Missing fallback metadata must not relabel existing vectors at a new width."""
    monkeypatch.delenv("HEBB_ALLOW_EMBED_DROP", raising=False)
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await conn.execute(
            "CREATE TABLE memory_embeddings (memory_id TEXT PRIMARY KEY, partition_id TEXT, embedding BLOB)"
        )
        embedding = np.zeros(384, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) VALUES ('legacy', 'default', ?)",
            (embedding,),
        )
        await conn.commit()

        with pytest.raises(EmbeddingDimensionMismatchError, match="384"):
            await initialize_schema(conn, embedding_dim=512)

        assert await _vec_row_count_proxy(conn) == 1
        meta_cursor = await conn.execute("SELECT value FROM schema_meta WHERE key = 'embedding_dim'")
        assert await meta_cursor.fetchone() is None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_fallback_metadata_read_error_fails_closed(tmp_path: Any) -> None:
    """A broken metadata table must not be treated as an absent metadata key."""
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await conn.execute(
            "CREATE TABLE memory_embeddings (memory_id TEXT PRIMARY KEY, partition_id TEXT, embedding BLOB)"
        )
        await conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY)")
        embedding = np.zeros(384, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) VALUES ('legacy', 'default', ?)",
            (embedding,),
        )
        await conn.commit()

        with pytest.raises(EmbeddingSchemaMigrationError, match="metadata"):
            await _ensure_vec_table(conn, embedding_dim=384)

        assert await _vec_row_count_proxy(conn) == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_embedding_schema_inspection_error_preserves_data_and_meta(tmp_path: Any, monkeypatch: Any) -> None:
    """A schema-query failure must not fall through to fallback initialization."""
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await initialize_schema(conn, embedding_dim=384)
        await _populate_one_vector(conn, 384)
        original_execute = conn.execute
        failed = False

        async def fail_embedding_schema_query(sql: str, *args: Any) -> Any:
            nonlocal failed
            if not failed and "sqlite_master" in sql and "memory_embeddings" in sql:
                failed = True
                raise RuntimeError("injected schema inspection failure")
            return await original_execute(sql, *args)

        monkeypatch.setattr(conn, "execute", fail_embedding_schema_query)

        with pytest.raises(EmbeddingSchemaMigrationError, match="inspect"):
            await initialize_schema(conn, embedding_dim=512)

        assert await _vec_row_count_proxy(conn) == 1
        meta_cursor = await conn.execute("SELECT value FROM schema_meta WHERE key = 'embedding_dim'")
        meta_row = await meta_cursor.fetchone()
        assert meta_row is not None
        assert meta_row[0] == "384"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_opt_in_rebuild_rolls_back_when_metadata_write_fails(tmp_path: Any, monkeypatch: Any) -> None:
    """A failed destructive rebuild restores the original populated table."""
    monkeypatch.setenv("HEBB_ALLOW_EMBED_DROP", "1")
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await conn.execute(
            "CREATE TABLE memory_embeddings (memory_id TEXT PRIMARY KEY, partition_id TEXT, embedding BLOB)"
        )
        await conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY)")
        embedding = np.zeros(384, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) VALUES ('legacy', 'default', ?)",
            (embedding,),
        )
        await conn.commit()

        with pytest.raises(EmbeddingSchemaMigrationError, match="rolled back"):
            await _ensure_vec_table(conn, embedding_dim=512)

        assert await _vec_row_count_proxy(conn) == 1
        row_cursor = await conn.execute("SELECT memory_id, partition_id, embedding FROM memory_embeddings")
        row = await row_cursor.fetchone()
        assert tuple(row) == ("legacy", "default", embedding)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_opt_in_savepoint_failure_preserves_data_and_meta(tmp_path: Any, monkeypatch: Any) -> None:
    """Failure to start a destructive rebuild must leave the old index intact."""
    monkeypatch.setenv("HEBB_ALLOW_EMBED_DROP", "1")
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await initialize_schema(conn, embedding_dim=384)
        await _populate_one_vector(conn, 384)
        original_execute = conn.execute
        failed = False

        async def fail_rebuild_savepoint(sql: str, *args: Any) -> Any:
            nonlocal failed
            if not failed and sql == "SAVEPOINT rebuild_memory_embeddings":
                failed = True
                raise RuntimeError("injected savepoint failure")
            return await original_execute(sql, *args)

        monkeypatch.setattr(conn, "execute", fail_rebuild_savepoint)

        with pytest.raises(EmbeddingSchemaMigrationError, match="start"):
            await initialize_schema(conn, embedding_dim=512)

        assert await _vec_row_count_proxy(conn) == 1
        meta_cursor = await conn.execute("SELECT value FROM schema_meta WHERE key = 'embedding_dim'")
        meta_row = await meta_cursor.fetchone()
        assert meta_row is not None
        assert meta_row[0] == "384"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_inconsistent_legacy_fallback_rebuilds_with_opt_in(tmp_path: Any, monkeypatch: Any) -> None:
    """Explicit opt-in permits rebuilding fallback vectors of unknown width."""
    monkeypatch.setenv("HEBB_ALLOW_EMBED_DROP", "1")
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path, load_vec=False)
    try:
        await conn.execute(
            "CREATE TABLE memory_embeddings (memory_id TEXT PRIMARY KEY, partition_id TEXT, embedding BLOB)"
        )
        await conn.executemany(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) VALUES (?, 'default', ?)",
            [
                ("legacy-384", np.zeros(384, dtype=np.float32).tobytes()),
                ("legacy-512", np.zeros(512, dtype=np.float32).tobytes()),
            ],
        )
        await conn.commit()

        await initialize_schema(conn, embedding_dim=768)

        assert await _vec_row_count_proxy(conn) == 0
        meta_cursor = await conn.execute("SELECT value FROM schema_meta WHERE key = 'embedding_dim'")
        meta_row = await meta_cursor.fetchone()
        assert meta_row is not None
        assert meta_row[0] == "768"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_populated_legacy_vec_table_without_partition_is_preserved(tmp_path: Any, monkeypatch: Any) -> None:
    """A failed legacy-schema probe must never silently discard vectors."""
    monkeypatch.delenv("HEBB_ALLOW_EMBED_DROP", raising=False)
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path)
    try:
        await conn.execute(
            "CREATE VIRTUAL TABLE memory_embeddings USING vec0(memory_id TEXT PRIMARY KEY, embedding float[384])"
        )
        embedding = np.zeros(384, dtype=np.float32).tobytes()
        await conn.execute(
            "INSERT INTO memory_embeddings(memory_id, embedding) VALUES ('legacy', ?)",
            (embedding,),
        )
        await conn.commit()

        with pytest.raises(EmbeddingSchemaMigrationError, match="partition_id"):
            await initialize_schema(conn, embedding_dim=384)

        assert await _vec_row_count_proxy(conn) == 1
        schema_cursor = await conn.execute("SELECT sql FROM sqlite_master WHERE name = 'memory_embeddings'")
        schema_row = await schema_cursor.fetchone()
        assert schema_row is not None
        assert "partition_id" not in schema_row[0]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_empty_legacy_vec_table_without_partition_is_rebuilt(tmp_path: Any) -> None:
    """An incompatible vec0 schema may be rebuilt when it contains no data."""
    db_path = str(tmp_path / "hebb.db")
    conn = await get_connection(db_path)
    try:
        await conn.execute(
            "CREATE VIRTUAL TABLE memory_embeddings USING vec0(memory_id TEXT PRIMARY KEY, embedding float[384])"
        )

        await initialize_schema(conn, embedding_dim=384)

        info_cursor = await conn.execute("PRAGMA table_info(memory_embeddings)")
        columns = {row[1] for row in await info_cursor.fetchall()}
        assert "partition_id" in columns
    finally:
        await conn.close()


async def _vec_row_count_proxy(conn: Any) -> int:
    """Count rows in ``memory_embeddings`` directly on the connection."""
    cursor = await conn.execute("SELECT count(*) FROM memory_embeddings")
    row = await cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0
