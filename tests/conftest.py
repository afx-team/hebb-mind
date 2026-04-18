"""Shared test fixtures."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from hippocampus.config.settings import Settings
from hippocampus.storage.migrations import get_connection, initialize_schema
from hippocampus.storage.partition_store import SQLitePartitionStore
from hippocampus.storage.sqlite_store import SQLiteMemoryStore


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        db_path=str(tmp_path / "test.db"),
        kg_path=str(tmp_path / "test_kg.json"),
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
