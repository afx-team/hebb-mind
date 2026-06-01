"""Shared test fixtures.

Layout note: tests mirror ``src/hebb/`` under ``tests/{unit,integration,e2e}``
plus ``tests/eval`` for the ``eval/`` harness. This root conftest holds the
fixtures shared across layers (sqlite stores + the in-process LLM/embedder
stubs); layer- or module-specific helpers stay next to their tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from hebb.agents.llm_client import LLMClient
from hebb.config.settings import Settings
from hebb.embedding.local import NoopEmbedder
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


@pytest_asyncio.fixture
async def db(settings: Settings):
    conn = await get_connection(settings.db_path)
    await initialize_schema(conn, settings.embedding_dim)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def memory_store(db) -> SQLiteMemoryStore:
    return SQLiteMemoryStore(db)


@pytest_asyncio.fixture
async def partition_store(db) -> SQLitePartitionStore:
    store = SQLitePartitionStore(db)
    await store.ensure_defaults()
    return store
