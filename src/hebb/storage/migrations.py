"""Database schema initialization and sqlite-vec extension loading."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_VEC_FIX_HINT = (
    "Vector search requires SQLite extension loading, which is disabled "
    "in some Python builds (notably macOS python.org installer). "
    "Fix: pip install pysqlite3"
)

# Matches the declared vec0 embedding width, e.g. ``embedding float[384]``,
# inside the CREATE VIRTUAL TABLE SQL recorded in ``sqlite_master``.
_VEC_DIM_RE = re.compile(r"embedding\s+float\[(\d+)\]", re.IGNORECASE)

# Opt-in escape hatch: when set to "1", a true embedding-dimension mismatch on a
# populated table is resolved by dropping the table (losing every vector) instead
# of raising. Off by default so a config change never silently wipes embeddings.
_ALLOW_EMBED_DROP_ENV = "HEBB_ALLOW_EMBED_DROP"


class EmbeddingDimensionMismatchError(RuntimeError):
    """Raised when an existing populated vec0 table's width != the configured dim.

    Dropping the table would discard every stored embedding, so we refuse and
    point the operator at ``hebb memory reembed`` (or the explicit opt-in env
    var) rather than silently rebuilding an empty index.
    """


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


async def _declared_vec_dim(db: aiosqlite.Connection) -> int | None:
    """Width declared in the existing ``memory_embeddings`` CREATE statement.

    Args:
        db: Open database connection.

    Returns:
        The integer dimension parsed from ``sqlite_master``, or ``None`` if the
        table is absent or is the regular-BLOB fallback (no fixed width).
    """
    try:
        cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name = 'memory_embeddings'")
        row = await cursor.fetchone()
    except Exception:  # pragma: no cover - sqlite_master is always present
        return None
    if row and row[0]:
        match = _VEC_DIM_RE.search(row[0])
        if match:
            return int(match.group(1))
    return None


async def _vec_row_count(db: aiosqlite.Connection) -> int:
    """Number of stored embeddings, or 0 if the table is missing/unreadable."""
    try:
        cursor = await db.execute("SELECT count(*) FROM memory_embeddings")
        row = await cursor.fetchone()
    except Exception:
        return 0
    return int(row[0]) if row and row[0] is not None else 0


async def _ensure_vec_table(db: aiosqlite.Connection, embedding_dim: int) -> None:
    """Create or recreate vec0 table if dimension or schema changed.

    Schema invariant: ``(memory_id, partition_id, embedding)``. The
    ``partition_id`` metadata column lets retrieval push the partition
    filter into the MATCH WHERE clause — without it, vec0 KNN is global
    and small partitions get starved by docs from larger ones.

    A *true* dimension mismatch on an EXISTING, POPULATED table is treated as
    a fatal, recoverable condition: dropping it would lose every vector, so we
    raise :class:`EmbeddingDimensionMismatchError` (run ``hebb memory reembed``
    or set ``HEBB_ALLOW_EMBED_DROP=1`` to opt into the destructive rebuild).
    First-time creation and the additive ``partition_id`` migration (empty or
    correctly-dimensioned tables) are unaffected.

    Args:
        db: Open database connection.
        embedding_dim: Target embedding width for the configured model.

    Raises:
        EmbeddingDimensionMismatchError: Populated table with a different width
            and no ``HEBB_ALLOW_EMBED_DROP=1`` opt-in.
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
        return
    except Exception:
        pass

    # Probe failed. Distinguish a benign schema gap (missing partition_id, or an
    # empty table) from a TRUE dimension mismatch on data we'd be destroying.
    declared = await _declared_vec_dim(db)
    row_count = await _vec_row_count(db)
    true_dim_mismatch = declared is not None and declared != dim

    if true_dim_mismatch and row_count > 0 and os.getenv(_ALLOW_EMBED_DROP_ENV) != "1":
        raise EmbeddingDimensionMismatchError(
            f"memory_embeddings has {row_count} vectors of width {declared}, but the "
            f"configured embedding dimension is {dim}. Dropping the table would lose "
            f"every embedding. Run `hebb memory reembed` to rebuild vectors at the new "
            f"dimension, or set {_ALLOW_EMBED_DROP_ENV}=1 to drop and rebuild empty."
        )

    if true_dim_mismatch and row_count > 0:
        logger.warning(
            "Dropping %d embeddings: dim %d -> %d (%s=1 opt-in)",
            row_count,
            declared,
            dim,
            _ALLOW_EMBED_DROP_ENV,
        )
    else:
        logger.warning(
            "Recreating vec0 table (dim=%d, partition_id column) — any existing embeddings will be lost",
            dim,
        )
    await db.execute("DROP TABLE IF EXISTS memory_embeddings")
    await db.execute(_VEC_CREATE_SQL.format(dim=dim))


async def _ensure_fallback_partition_column(db: aiosqlite.Connection) -> None:
    """Ensure the non-vec0 fallback ``memory_embeddings`` table carries ``partition_id``.

    Only acts on the regular (BLOB) fallback table — an existing vec0 virtual
    table is migrated by :func:`_ensure_vec_table`. Writes always supply
    ``partition_id`` (the partition-aware vector-KNN contract), so a fallback
    table created before that contract needs an additive ``ALTER`` rather than
    a destructive recreate, else every insert fails with
    ``no such column: partition_id`` in vec0-unavailable environments.

    Args:
        db: Open database connection.
    """
    cursor = await db.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'memory_embeddings'"
    )
    row = await cursor.fetchone()
    if not row or not row[0] or "USING vec0" in row[0]:
        # vec0 virtual table (or absent) — schema maintained by _ensure_vec_table.
        return

    info_cursor = await db.execute("PRAGMA table_info(memory_embeddings)")
    columns = {r[1] for r in await info_cursor.fetchall()}
    if "partition_id" not in columns:
        await db.execute(
            "ALTER TABLE memory_embeddings "
            "ADD COLUMN partition_id TEXT NOT NULL DEFAULT 'default'"
        )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_embeddings_partition_id "
        "ON memory_embeddings(partition_id)"
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
        except EmbeddingDimensionMismatchError:
            # A populated table with a mismatched width is operator-actionable,
            # not a missing-extension fallback — surface it instead of silently
            # degrading to a dimensionless BLOB table. No data was dropped: the
            # raise happens before any DROP. (write F7 / embedding F7)
            raise
        except Exception as e:
            logger.warning("Could not create vec0 table: %s. %s", e, _VEC_FIX_HINT)
            # Fallback: regular table so embedding INSERT/DELETE still works.
            # Schema mirrors the vec0 contract (memory_id, partition_id,
            # embedding) so partition-aware writes don't fail in
            # vec0-unavailable environments.
            await db.execute(
                "CREATE TABLE IF NOT EXISTS memory_embeddings ("
                "memory_id TEXT PRIMARY KEY, "
                "partition_id TEXT NOT NULL DEFAULT 'default', "
                "embedding BLOB)"
            )

    # Additive migration for fallback tables created before the partition_id
    # write contract (vec0 tables are skipped inside). Idempotent.
    await _ensure_fallback_partition_column(db)

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
