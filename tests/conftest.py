"""Shared test fixtures.

Layout note: tests mirror ``src/hebb/`` under ``tests/{unit,integration,e2e}``
plus ``tests/eval`` for the ``eval/`` harness. This root conftest holds the
fixtures shared across layers (sqlite stores + the in-process LLM/embedder
stubs); layer- or module-specific helpers stay next to their tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import aiosqlite
import pytest
import pytest_asyncio

from hebb.agents.llm_client import LLMClient
from hebb.config.settings import Settings
from hebb.embedding.local import NoopEmbedder
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.storage.migrations import get_connection, initialize_schema
from hebb.storage.partition_store import SQLitePartitionStore
from hebb.storage.sqlite_store import SQLiteMemoryStore


@pytest.fixture
def mock_llm() -> AsyncMock:
    """An ``LLMClient`` double — set ``.complete_json.return_value`` / ``.side_effect`` per test."""
    return AsyncMock(spec=LLMClient)


@pytest.fixture
def noop_embedder() -> NoopEmbedder:
    """Zero-vector embedder (no model download) for in-process retrieval/agent tests."""
    return NoopEmbedder(384)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        home_dir=tmp_path,
        llm_model="openai/gpt-4o-mini",
    )


@pytest.fixture
def shared_lock() -> asyncio.Lock:
    """Process-level write lock shared between store and KG (Issue #36)."""
    return asyncio.Lock()


@pytest_asyncio.fixture
async def db(settings: Settings, shared_lock: asyncio.Lock) -> AsyncIterator[aiosqlite.Connection]:
    conn = await get_connection(settings.db_path)
    await initialize_schema(conn, settings.embedding_dim)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def memory_store(
    db: aiosqlite.Connection, shared_lock: asyncio.Lock
) -> SQLiteMemoryStore:
    return SQLiteMemoryStore(db, write_lock=shared_lock)


@pytest_asyncio.fixture
async def partition_store(
    db: aiosqlite.Connection, shared_lock: asyncio.Lock
) -> SQLitePartitionStore:
    store = SQLitePartitionStore(db, write_lock=shared_lock)
    await store.ensure_defaults()
    return store


@pytest_asyncio.fixture
async def knowledge_graph(tmp_path: Path, shared_lock: asyncio.Lock) -> KnowledgeGraph:
    """Knowledge graph sharing the process-level write lock (Issue #36)."""
    return KnowledgeGraph(tmp_path / "kg.json", lock=shared_lock)
