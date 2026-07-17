"""Storage backend factory — creates the appropriate stores based on config."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from hebb.config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class StorageContext:
    """Holds initialized storage backends and their cleanup function."""

    memory_store: Any  # MemoryStore protocol
    partition_store: Any  # PartitionStore protocol
    close: Callable[[], Coroutine[Any, Any, None]]  # async cleanup
    # Shared process-level write lock for SQLite backend (Issue #36).
    # ``None`` for PostgreSQL (pool-based, no shared lock needed).
    write_lock: asyncio.Lock | None = None


async def create_stores(settings: Settings) -> StorageContext:
    """Create storage backends based on settings.storage_type.

    Supports:
        - "sqlite": SQLite + sqlite-vec (default, zero-config)
        - "postgresql": PostgreSQL + pgvector (production-grade)
    """
    backend = settings.storage_type.lower()

    if backend == "sqlite":
        return await _create_sqlite(settings)
    elif backend == "postgresql":
        return await _create_postgresql(settings)
    else:
        raise ValueError(f"Unknown storage_type: {settings.storage_type!r}. Use 'sqlite' or 'postgresql'.")


async def _create_sqlite(settings: Settings) -> StorageContext:
    from hebb.storage.migrations import get_connection, initialize_schema
    from hebb.storage.partition_store import SQLitePartitionStore
    from hebb.storage.sqlite_store import SQLiteMemoryStore

    db = await get_connection(settings.db_path, load_vec=settings.embedding_enabled)
    # Unified process-level write lock shared across SQLiteMemoryStore,
    # SQLitePartitionStore, and KnowledgeGraph so that every SQL mutation
    # and its corresponding graph mutation form a single crash-consistent
    # critical section (Issue #36, audit C1). The lock prevents
    # interleaving between background tasks (consolidation / forgetting)
    # and request handlers that share the same connection.
    shared_lock = asyncio.Lock()
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await initialize_schema(db, settings.embedding_dim, create_vec_table=settings.embedding_enabled)

    memory_store = SQLiteMemoryStore(db, write_lock=shared_lock)
    partition_store = SQLitePartitionStore(db, write_lock=shared_lock)

    async def close() -> None:
        await db.close()

    logger.info("Storage backend: SQLite (%s)", settings.db_path)
    return StorageContext(
        memory_store=memory_store,
        partition_store=partition_store,
        close=close,
        write_lock=shared_lock,
    )


async def _create_postgresql(settings: Settings) -> StorageContext:
    if not settings.pg_url:
        raise ValueError("PostgreSQL storage requires pg_url. Run: hebb config set pg_url <postgresql-url>")

    try:
        import asyncpg
    except ImportError:
        raise ImportError("PostgreSQL backend requires asyncpg and pgvector. Install with: pip install hebb-mind[pg]")

    from hebb.storage.pg_migrations import initialize_pg_schema
    from hebb.storage.pg_store import PGMemoryStore, PGPartitionStore

    pool = await asyncpg.create_pool(
        settings.pg_url,
        min_size=settings.pg_pool_min,
        max_size=settings.pg_pool_max,
    )

    await initialize_pg_schema(pool, settings.embedding_dim)

    memory_store = PGMemoryStore(pool)
    partition_store = PGPartitionStore(pool)

    async def close() -> None:
        await pool.close()

    logger.info("Storage backend: PostgreSQL (pool %d-%d)", settings.pg_pool_min, settings.pg_pool_max)
    return StorageContext(memory_store=memory_store, partition_store=partition_store, close=close)
