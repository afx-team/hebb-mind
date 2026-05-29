"""Database schema initialization and sqlite-vec extension loading."""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_VEC_FIX_HINT = (
    "Vector search requires SQLite extension loading, which is disabled "
    "in some Python builds (notably macOS python.org installer). "
    "Fix: pip install pysqlite3"
)


async def get_connection(db_path: str, *, load_vec: bool = True) -> aiosqlite.Connection:
    """Open a connection with WAL mode, foreign keys, and sqlite-vec loaded.

    Note: ``hebb.storage._sqlite_compat`` patches ``sys.modules["sqlite3"]``
    with ``pysqlite3`` on platforms that lack extension loading support.
    This means ``aiosqlite`` (which imports ``sqlite3``) transparently uses the
    patched module, and ``conn.enable_load_extension`` is always available
    when ``pysqlite3-binary`` is installed.
    """
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    if load_vec:
        try:
            import sqlite_vec

            def _load_vec(conn: Any) -> None:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)

            await db.execute("select 1")  # ensure connection is initialized
            await db._execute(_load_vec, db._connection)  # type: ignore[no-untyped-call]
        except (AttributeError, ImportError, OSError) as e:
            logger.warning("sqlite-vec unavailable (%s), vector search disabled. %s", e, _VEC_FIX_HINT)

    return db


_VEC_CREATE_SQL = (
    "CREATE VIRTUAL TABLE memory_embeddings USING vec0("
    "memory_id TEXT PRIMARY KEY, partition_id TEXT, embedding float[{dim}])"
)

_FTS_CREATE_SQL = (
    "CREATE VIRTUAL TABLE memory_fts USING fts5("
    "memory_id UNINDEXED, partition_id UNINDEXED, content, "
    "tokenize='porter unicode61')"
)


async def _ensure_fts_table(db: aiosqlite.Connection) -> None:
    """Create FTS5 with partition_id, force-rebuild if old schema present."""
    try:
        await db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5("
            "memory_id UNINDEXED, partition_id UNINDEXED, content, "
            "tokenize='porter unicode61')"
        )
    except Exception as e:
        logger.warning("Could not create FTS5 table: %s", e)
        return

    # Schema probe: insert a sentinel row using the new 3-column form. If
    # the existing FTS5 table lacks partition_id, this raises and we
    # rebuild. Otherwise we delete the probe and move on.
    try:
        await db.execute(
            "INSERT INTO memory_fts(memory_id, partition_id, content) "
            "VALUES ('__schema_probe__', '__probe__', '__probe__')"
        )
        await db.execute("DELETE FROM memory_fts WHERE memory_id = '__schema_probe__'")
    except Exception:
        logger.warning("Recreating FTS5 table (partition_id column missing) — any existing FTS index will be lost")
        await db.execute("DROP TABLE IF EXISTS memory_fts")
        await db.execute(_FTS_CREATE_SQL)


async def _ensure_vec_table(db: aiosqlite.Connection, embedding_dim: int) -> None:
    """Create or recreate vec0 table if dimension or schema changed.

    Schema invariant: ``(memory_id, partition_id, embedding)``. The
    ``partition_id`` metadata column lets retrieval push the partition
    filter into the MATCH WHERE clause — without it, vec0 KNN is global
    and small partitions get starved by docs from larger ones.
    """
    import numpy as np

    dim = int(embedding_dim)
    # Fast path for fresh DB
    try:
        await db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0("
            f"memory_id TEXT PRIMARY KEY, partition_id TEXT, embedding float[{dim}])"
        )
    except Exception:
        pass

    # Probe both the dimension AND the partition_id column. A pre-refactor
    # table (no partition_id) succeeds at CREATE IF NOT EXISTS silently;
    # this insert raises iff the column is missing or the dim mismatches.
    probe = np.zeros(dim, dtype=np.float32).tobytes()
    try:
        await db.execute(
            "INSERT INTO memory_embeddings(memory_id, partition_id, embedding) "
            "VALUES ('__schema_probe__', '__probe__', ?)",
            (probe,),
        )
        await db.execute("DELETE FROM memory_embeddings WHERE memory_id = '__schema_probe__'")
    except Exception:
        logger.warning(
            "Recreating vec0 table (dim=%d, partition_id column) — any existing embeddings will be lost",
            dim,
        )
        await db.execute("DROP TABLE IF EXISTS memory_embeddings")
        await db.execute(_VEC_CREATE_SQL.format(dim=dim))


async def initialize_schema(
    db: aiosqlite.Connection, embedding_dim: int = 384, *, create_vec_table: bool = True
) -> None:
    """Create all tables idempotently."""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS partitions (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            enabled     INTEGER NOT NULL DEFAULT 1,
            is_system   INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS memories (
            id                TEXT PRIMARY KEY,
            partition_id      TEXT NOT NULL,
            content           TEXT NOT NULL,
            importance_score  REAL NOT NULL DEFAULT 5.0,
            tags              TEXT NOT NULL DEFAULT '[]',
            metadata          TEXT NOT NULL DEFAULT '{}',
            source            TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
            last_accessed_at  TEXT NOT NULL DEFAULT (datetime('now')),
            access_count      INTEGER NOT NULL DEFAULT 0,
            expires_at        TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_memories_partition ON memories(partition_id);
        CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
        CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed_at);
        CREATE INDEX IF NOT EXISTS idx_memories_expires_at ON memories(expires_at);
    """)

    # sqlite-vec virtual table (cannot be created via executescript)
    if create_vec_table:
        try:
            # Check if vec0 table exists with a different dimension
            await _ensure_vec_table(db, embedding_dim)
        except Exception as e:
            logger.warning("Could not create vec0 table: %s. %s", e, _VEC_FIX_HINT)
            # Fallback: regular table so embedding INSERT/DELETE still works
            await db.execute(
                "CREATE TABLE IF NOT EXISTS memory_embeddings (memory_id TEXT PRIMARY KEY, embedding BLOB)"
            )

    # FTS5 full-text search table for keyword matching.
    # `porter unicode61` chains Porter stemming on top of unicode61 so that
    # plural/inflected forms match the query stem ("researched" matches
    # "research"). Without stemming, BM25 misses on conjugated verbs.
    #
    # Schema invariant: ``(memory_id, partition_id, content)``. The
    # ``partition_id`` column is UNINDEXED — FTS5 stores it but doesn't
    # tokenize it; it stays usable in the WHERE clause alongside MATCH,
    # so partition filtering pushes into the BM25 ranking step instead
    # of being a post-filter that starves small partitions globally.
    await _ensure_fts_table(db)

    await db.commit()
