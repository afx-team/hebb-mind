"""Database schema initialization and sqlite-vec extension loading."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)


def _get_loadable_sqlite3():
    """Return a sqlite3 module that supports extension loading.

    The standard sqlite3 on some platforms (notably macOS python.org builds)
    is compiled without extension loading support. We try pysqlite3 as a
    fallback, which bundles a full SQLite and always supports extensions.
    """
    import sqlite3

    # Fast path: check if the standard module supports extensions
    test_conn = sqlite3.connect(":memory:")
    if hasattr(test_conn, "enable_load_extension"):
        test_conn.close()
        return sqlite3
    test_conn.close()

    # Fallback: try pysqlite3-binary which always supports extensions
    try:
        import pysqlite3  # type: ignore[import-untyped]

        test_conn = pysqlite3.connect(":memory:")
        if hasattr(test_conn, "enable_load_extension"):
            test_conn.close()
            logger.info("Using pysqlite3 for sqlite-vec extension loading")
            return pysqlite3
        test_conn.close()
    except ImportError:
        pass

    logger.warning(
        "No SQLite with extension loading found. "
        "Install pysqlite3-binary for vector search support: "
        "pip install pysqlite3-binary"
    )
    return None


async def get_connection(db_path: str, *, load_vec: bool = True) -> aiosqlite.Connection:
    """Open a connection with WAL mode, foreign keys, and sqlite-vec loaded."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    if load_vec:
        try:
            import sqlite_vec

            sqlite3_mod = _get_loadable_sqlite3()

            if sqlite3_mod is not None:

                def _load_vec(conn):
                    conn.enable_load_extension(True)
                    sqlite_vec.load(conn)
                    conn.enable_load_extension(False)

                await db.execute("select 1")  # ensure connection is initialized
                await db._execute(_load_vec, db._connection)
            else:
                logger.warning("sqlite-vec unavailable (no SQLite with extension loading), vector search disabled")
        except (AttributeError, ImportError, OSError) as e:
            logger.warning("sqlite-vec unavailable (%s), vector search disabled", e)

    return db


async def _ensure_vec_table(db: aiosqlite.Connection, embedding_dim: int) -> None:
    """Create or recreate vec0 table if dimension changed."""
    dim = int(embedding_dim)
    # Try creating the table first (fast path)
    try:
        await db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0("
            f"memory_id TEXT PRIMARY KEY, embedding float[{dim}])"
        )
    except Exception:
        # Table exists but may have different dimension — test with a probe
        try:
            import numpy as np

            probe = np.zeros(dim, dtype=np.float32).tobytes()
            await db.execute(
                "INSERT INTO memory_embeddings(memory_id, embedding) VALUES ('__dim_probe__', ?)", (probe,)
            )
            await db.execute("DELETE FROM memory_embeddings WHERE memory_id = '__dim_probe__'")
        except Exception:
            # Dimension mismatch — recreate table (loses existing embeddings)
            logger.warning(
                "Embedding dimension changed to %d, recreating vec0 table (existing vectors will be lost)", dim
            )
            await db.execute("DROP TABLE IF EXISTS memory_embeddings")
            await db.execute(
                f"CREATE VIRTUAL TABLE memory_embeddings USING vec0("
                f"memory_id TEXT PRIMARY KEY, embedding float[{dim}])"
            )


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