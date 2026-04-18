"""Database schema initialization and sqlite-vec extension loading."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def get_connection(db_path: str, *, load_vec: bool = True) -> aiosqlite.Connection:
    """Open a connection with WAL mode, foreign keys, and sqlite-vec loaded."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    if load_vec:
        try:
            import sqlite_vec

            def _load_vec(conn):
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)

            await db.execute("select 1")  # ensure connection is initialized
            await db._execute(_load_vec, db._connection)
        except (AttributeError, ImportError, OSError) as e:
            logger.warning("sqlite-vec unavailable (%s), vector search disabled", e)

    return db


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
            await db.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0("
                f"memory_id TEXT PRIMARY KEY, embedding float[{int(embedding_dim)}])"
            )
        except Exception as e:
            logger.warning("Could not create vec0 table: %s", e)
            # Fallback: regular table so embedding INSERT/DELETE still works
            await db.execute(
                "CREATE TABLE IF NOT EXISTS memory_embeddings ("
                "memory_id TEXT PRIMARY KEY, embedding BLOB)"
            )

    # FTS5 full-text search table for keyword matching
    # unicode61 tokenizer handles CJK via bigram, works cross-platform
    try:
        await db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5("
            "memory_id UNINDEXED, content, tokenize='unicode61')"
        )
    except Exception as e:
        logger.warning("Could not create FTS5 table: %s", e)

    await db.commit()
