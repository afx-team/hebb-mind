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

# Opt-in escape hatch: when set to "1", an incompatible populated embeddings
# table may be dropped and rebuilt empty. Off by default so migrations never
# silently wipe embeddings.
_ALLOW_EMBED_DROP_ENV = "HEBB_ALLOW_EMBED_DROP"


class EmbeddingSchemaMigrationError(RuntimeError):
    """Raised when migrating ``memory_embeddings`` would discard stored vectors.

    The existing table is left unchanged. Operators can rebuild embeddings with
    ``hebb memory reembed`` or explicitly allow an empty rebuild by setting
    ``HEBB_ALLOW_EMBED_DROP=1``.
    """


class EmbeddingDimensionMismatchError(EmbeddingSchemaMigrationError):
    """Raised when a populated embeddings table's width != the configured dim.

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

    Args:
        db_path: Filesystem path to the SQLite database.
        load_vec: Whether to attempt loading the sqlite-vec extension. When
            false or unavailable, schema initialization uses a BLOB fallback.

    Returns:
        Configured asynchronous SQLite connection.

    Raises:
        Exception: Opening or configuring the SQLite database failed.
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

# Regular (BLOB) fallback table used when the vec0 extension can't be loaded
# (e.g. macOS python.org builds without loadable-extension support). Mirrors
# the vec0 contract (memory_id, partition_id, embedding) so partition-aware
# writes don't fail in vec0-unavailable environments. The BLOB column has no
# fixed width, so the configured width is recorded in ``schema_meta`` (see
# ``_read_meta_dim``) to preserve the dim guard on this path.
_FALLBACK_CREATE_SQL = (
    "CREATE TABLE IF NOT EXISTS memory_embeddings ("
    "memory_id TEXT PRIMARY KEY, "
    "partition_id TEXT NOT NULL DEFAULT 'default', "
    "embedding BLOB)"
)

# Key/value row recording the embedding width the current ``memory_embeddings``
# table was built at. vec0 declares the width inline (``float[N]``) so this is
# only authoritative for the BLOB fallback, but it is written in both cases so
# the write-path dim guard and the migration mismatch check still work on the
# fallback path (where ``sqlite_master`` has no width to read).
_META_CREATE_SQL = "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
_META_DIM_KEY = "embedding_dim"


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
    """Return the number of stored embeddings.

    Args:
        db: Open database connection with an existing embeddings table.

    Returns:
        Number of rows in ``memory_embeddings``.

    Raises:
        EmbeddingSchemaMigrationError: The table exists but cannot be read. An
            unreadable table must never be treated as empty during migration.
    """
    try:
        cursor = await db.execute("SELECT count(*) FROM memory_embeddings")
        row = await cursor.fetchone()
    except Exception as e:
        raise EmbeddingSchemaMigrationError(
            "Could not determine whether memory_embeddings contains data; "
            "refusing to rebuild it because stored embeddings may be lost. "
            f"Restore sqlite-vec access and retry, or set {_ALLOW_EMBED_DROP_ENV}=1 "
            "to explicitly allow a destructive rebuild."
        ) from e
    return int(row[0]) if row and row[0] is not None else 0


async def _embedding_table_schema(db: aiosqlite.Connection) -> tuple[str | None, set[str]]:
    """Read the embeddings table declaration and columns without mutating it.

    Args:
        db: Open database connection.

    Returns:
        A pair of the ``sqlite_master`` CREATE statement and declared column
        names. The CREATE statement is ``None`` when the table does not exist.

    Raises:
        EmbeddingSchemaMigrationError: The existing table cannot be inspected.
    """
    try:
        cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'memory_embeddings'")
        row = await cursor.fetchone()
        if not row or not row[0]:
            return None, set()

        create_sql = str(row[0])
        info_cursor = await db.execute("PRAGMA table_info(memory_embeddings)")
        columns = {str(info_row[1]) for info_row in await info_cursor.fetchall()}
    except Exception as e:
        raise EmbeddingSchemaMigrationError(
            "Could not inspect the existing memory_embeddings schema; refusing "
            "to rebuild it because stored embeddings may be lost. Restore "
            "sqlite-vec access and retry."
        ) from e
    return create_sql, columns


async def _read_meta_dim(db: aiosqlite.Connection) -> int | None:
    """Embedding width recorded in ``schema_meta``, or ``None`` if unset.

    Authoritative for the BLOB fallback table (which has no inline width);
    informational for vec0 (which declares its width inline). Returns ``None``
    when the meta table is absent or the key is unset — e.g. first init, or a
    DB created before this metadata existed.

    Args:
        db: Open database connection.

    Returns:
        Recorded positive embedding dimension, or ``None`` only when the table
        or metadata key does not exist.

    Raises:
        EmbeddingSchemaMigrationError: Metadata exists but cannot be read or is
            not a positive integer.
    """
    try:
        table_cursor = await db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'")
        if await table_cursor.fetchone() is None:
            return None
        cursor = await db.execute("SELECT value FROM schema_meta WHERE key = ?", (_META_DIM_KEY,))
        row = await cursor.fetchone()
        if row is None:
            return None
        if row[0] is None:
            raise ValueError("embedding dimension metadata is NULL")
        dim = int(row[0])
        if dim <= 0:
            raise ValueError("embedding dimension must be positive")
    except Exception as e:
        raise EmbeddingSchemaMigrationError(
            "Could not read valid embedding-dimension metadata from schema_meta; "
            "refusing to continue because relabeling existing vectors may corrupt "
            "the index. Repair the metadata table and retry."
        ) from e
    return dim


async def _infer_fallback_dim(db: aiosqlite.Connection) -> int | None:
    """Infer float32 width from all rows in a legacy BLOB fallback table.

    Args:
        db: Open database connection with a regular ``memory_embeddings`` table.

    Returns:
        The uniform float32 dimension, or ``None`` when the table is empty.

    Raises:
        EmbeddingSchemaMigrationError: Stored values are NULL, not BLOBs, have
            inconsistent lengths, have an invalid float32 byte width, or cannot
            be inspected.
    """
    try:
        cursor = await db.execute(
            "SELECT count(*), "
            "sum(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END), "
            "sum(CASE WHEN embedding IS NOT NULL AND typeof(embedding) != 'blob' THEN 1 ELSE 0 END), "
            "count(DISTINCT length(embedding)), min(length(embedding)), max(length(embedding)) "
            "FROM memory_embeddings"
        )
        row = await cursor.fetchone()
    except Exception as e:
        raise EmbeddingSchemaMigrationError(
            "Could not infer the dimension of legacy fallback embeddings; "
            "refusing to write new dimension metadata or rebuild the table."
        ) from e

    if row is None:
        raise EmbeddingSchemaMigrationError(
            "Could not infer the dimension of legacy fallback embeddings because "
            "the aggregate query returned no result."
        )
    row_count = int(row[0]) if row[0] is not None else 0
    if row_count == 0:
        return None

    null_count = int(row[1] or 0)
    non_blob_count = int(row[2] or 0)
    distinct_lengths = int(row[3] or 0)
    min_bytes = int(row[4]) if row[4] is not None else 0
    max_bytes = int(row[5]) if row[5] is not None else 0
    if null_count or non_blob_count or distinct_lengths != 1 or min_bytes != max_bytes:
        raise EmbeddingSchemaMigrationError(
            "Legacy fallback embeddings do not have one consistent non-NULL BLOB "
            "width; refusing to infer or overwrite embedding-dimension metadata."
        )
    if min_bytes <= 0 or min_bytes % 4 != 0:
        raise EmbeddingSchemaMigrationError(
            f"Legacy fallback embeddings have invalid byte width {min_bytes}; "
            "float32 vector bytes must be non-empty and divisible by 4."
        )
    return min_bytes // 4


async def _write_meta_dim(db: aiosqlite.Connection, dim: int) -> None:
    """Record (upsert) the embedding width the current table is built at."""
    await db.execute(_META_CREATE_SQL)
    await db.execute(
        "INSERT INTO schema_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (_META_DIM_KEY, str(dim)),
    )


async def _ensure_vec_table(db: aiosqlite.Connection, embedding_dim: int) -> None:
    """Create or recreate the vec0 table, or its BLOB fallback, at ``embedding_dim``.

    Schema invariant: ``(memory_id, partition_id, embedding)``. The
    ``partition_id`` metadata column lets retrieval push the partition
    filter into the MATCH WHERE clause — without it, vec0 KNN is global
    and small partitions get starved by docs from larger ones.

    A *true* dimension mismatch on an EXISTING, POPULATED table is treated as
    a fatal, recoverable condition: dropping it would lose every vector, so we
    raise :class:`EmbeddingDimensionMismatchError` (run ``hebb memory reembed``
    or set ``HEBB_ALLOW_EMBED_DROP=1`` to opt into the destructive rebuild).
    First-time creation and empty-table schema upgrades remain automatic. A
    regular BLOB fallback missing ``partition_id`` is migrated additively.

    The existing width is read from the vec0 declaration (``float[N]``) when the
    extension is available, or from ``schema_meta`` for the BLOB fallback used
    when vec0 can't be loaded (macOS python.org builds). Recording the width in
    ``schema_meta`` keeps the write-path dim guard and the migration mismatch
    check working on the fallback path too.

    Args:
        db: Open database connection.
        embedding_dim: Target embedding width for the configured model.

    Raises:
        EmbeddingSchemaMigrationError: A populated table requires destructive
            migration and no ``HEBB_ALLOW_EMBED_DROP=1`` opt-in was provided.
    """
    dim = int(embedding_dim)
    allow_drop = os.getenv(_ALLOW_EMBED_DROP_ENV) == "1"
    create_sql, columns = await _embedding_table_schema(db)
    table_exists = create_sql is not None
    is_vec = bool(create_sql and re.search(r"\bUSING\s+vec0\b", create_sql, re.IGNORECASE))
    declared = await _declared_vec_dim(db) if is_vec else None
    validation_error: EmbeddingSchemaMigrationError | None = None
    try:
        existing_dim = declared if declared is not None else await _read_meta_dim(db)
    except EmbeddingSchemaMigrationError as e:
        if not allow_drop:
            raise
        existing_dim = None
        validation_error = e

    # A regular fallback with the core columns is already usable. A missing
    # partition_id is handled additively by _ensure_fallback_partition_column,
    # so repeated initialization must never replace a populated fallback merely
    # because vec0 happens to be unavailable on this connection.
    required_columns = {"memory_id", "embedding"}
    fallback_compatible = not is_vec and required_columns <= columns
    vec_compatible = is_vec and "partition_id" in columns and declared is not None
    if table_exists and fallback_compatible and existing_dim is None and validation_error is None:
        try:
            existing_dim = await _infer_fallback_dim(db)
        except EmbeddingSchemaMigrationError as e:
            if not allow_drop:
                raise
            validation_error = e
    dim_mismatch = existing_dim is not None and existing_dim != dim

    incompatibility = (
        f"embedding dimension could not be validated: {validation_error}" if validation_error is not None else None
    )
    if table_exists:
        if incompatibility is not None:
            pass
        elif not required_columns <= columns:
            missing = ", ".join(sorted(required_columns - columns))
            incompatibility = f"missing required column(s): {missing}"
        elif is_vec and "partition_id" not in columns:
            incompatibility = "missing partition_id column"
        elif is_vec and declared is None:
            incompatibility = "embedding dimension is not declared"
        elif dim_mismatch:
            incompatibility = f"embedding dimension is {existing_dim}, configured dimension is {dim}"

    if table_exists and incompatibility is None and (fallback_compatible or vec_compatible):
        await _write_meta_dim(db, dim)
        return

    row_count: int | None = 0
    if table_exists:
        try:
            row_count = await _vec_row_count(db)
        except EmbeddingSchemaMigrationError:
            if not allow_drop:
                raise
            row_count = None

    if table_exists and row_count is not None and row_count > 0 and not allow_drop:
        if dim_mismatch:
            raise EmbeddingDimensionMismatchError(
                f"memory_embeddings has {row_count} vectors of width {existing_dim}, but the "
                f"configured embedding dimension is {dim}. Dropping the table would lose "
                f"every embedding. Run `hebb memory reembed` to rebuild vectors at the new "
                f"dimension, or set {_ALLOW_EMBED_DROP_ENV}=1 to drop and rebuild empty."
            )
        raise EmbeddingSchemaMigrationError(
            f"memory_embeddings has {row_count} stored vector(s), but its schema is "
            f"incompatible ({incompatibility}). Rebuilding it would lose every embedding. "
            "Run `hebb memory reembed` to rebuild the index, or set "
            f"{_ALLOW_EMBED_DROP_ENV}=1 to explicitly drop and rebuild empty."
        )

    try:
        await db.execute("SAVEPOINT rebuild_memory_embeddings")
    except Exception as e:
        raise EmbeddingSchemaMigrationError(
            "Could not start the memory_embeddings rebuild; the existing table was left unchanged."
        ) from e
    try:
        if table_exists:
            if row_count is None:
                logger.warning(
                    "Dropping unreadable memory_embeddings table (%s=1 opt-in)",
                    _ALLOW_EMBED_DROP_ENV,
                )
            elif row_count > 0:
                logger.warning(
                    "Dropping %d embeddings with incompatible schema (%s; %s=1 opt-in)",
                    row_count,
                    incompatibility,
                    _ALLOW_EMBED_DROP_ENV,
                )
            await db.execute("DROP TABLE memory_embeddings")

        try:
            await db.execute(_VEC_CREATE_SQL.format(dim=dim))
        except Exception:
            await db.execute(_FALLBACK_CREATE_SQL)
        await _write_meta_dim(db, dim)
    except BaseException as e:
        await db.execute("ROLLBACK TO SAVEPOINT rebuild_memory_embeddings")
        await db.execute("RELEASE SAVEPOINT rebuild_memory_embeddings")
        if not isinstance(e, Exception):
            raise
        raise EmbeddingSchemaMigrationError(
            "Could not rebuild memory_embeddings; the migration was rolled back and the previous table was preserved."
        ) from e
    else:
        await db.execute("RELEASE SAVEPOINT rebuild_memory_embeddings")


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
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE name = 'memory_embeddings'")
    row = await cursor.fetchone()
    if not row or not row[0] or "USING vec0" in row[0]:
        # vec0 virtual table (or absent) — schema maintained by _ensure_vec_table.
        return

    info_cursor = await db.execute("PRAGMA table_info(memory_embeddings)")
    columns = {r[1] for r in await info_cursor.fetchall()}
    if "partition_id" not in columns:
        await db.execute("ALTER TABLE memory_embeddings ADD COLUMN partition_id TEXT NOT NULL DEFAULT 'default'")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_memory_embeddings_partition_id ON memory_embeddings(partition_id)")


async def initialize_schema(
    db: aiosqlite.Connection, embedding_dim: int = 384, *, create_vec_table: bool = True
) -> None:
    """Create all database tables idempotently.

    Args:
        db: Open database connection.
        embedding_dim: Width of vectors produced by the configured embedder.
        create_vec_table: Whether to initialize the vector index or fallback.

    Returns:
        None.

    Raises:
        EmbeddingSchemaMigrationError: A populated embeddings table requires a
            destructive schema migration without explicit operator opt-in.
        Exception: A required SQLite schema operation failed.
    """
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

        -- Records the embedding width the memory_embeddings table was built at,
        -- so the dim guard and migration mismatch check work on the vec0-unavailable
        -- BLOB fallback (which has no inline width to read from sqlite_master).
        CREATE TABLE IF NOT EXISTS schema_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    # sqlite-vec virtual table (cannot be created via executescript)
    if create_vec_table:
        # _ensure_vec_table handles vec0 unavailability itself. Any other error
        # must fail closed: treating it as an unavailable extension could retain
        # old BLOBs while relabeling them with the newly configured dimension.
        await _ensure_vec_table(db, embedding_dim)

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
