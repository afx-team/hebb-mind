"""Tests for storage factory."""

from pathlib import Path

import pytest

from hippocampus.config.settings import Settings
from hippocampus.storage.factory import create_stores


class TestStorageFactory:
    @pytest.mark.asyncio
    async def test_sqlite_factory(self, tmp_path: Path):
        settings = Settings(storage_type="sqlite", home_dir=tmp_path)
        ctx = await create_stores(settings)
        assert ctx.memory_store is not None
        assert ctx.partition_store is not None
        # Verify it's actually SQLite
        from hippocampus.storage.sqlite_store import SQLiteMemoryStore

        assert isinstance(ctx.memory_store, SQLiteMemoryStore)
        await ctx.close()

    @pytest.mark.asyncio
    async def test_invalid_backend(self, tmp_path: Path):
        settings = Settings(storage_type="redis", home_dir=tmp_path)
        with pytest.raises(ValueError, match="Unknown storage_type"):
            await create_stores(settings)

    @pytest.mark.asyncio
    async def test_postgresql_missing_url(self):
        settings = Settings(storage_type="postgresql", pg_url=None)
        with pytest.raises(ValueError, match="pg_url"):
            await create_stores(settings)

    @pytest.mark.asyncio
    async def test_postgresql_missing_package(self, monkeypatch):
        """PG backend raises ImportError when asyncpg is not installed."""
        settings = Settings(storage_type="postgresql", pg_url="postgresql://localhost/test")
        import hippocampus.storage.factory as factory_mod

        async def _mock_pg(s):
            raise ImportError("asyncpg not installed")

        monkeypatch.setattr(factory_mod, "_create_postgresql", _mock_pg)
        with pytest.raises(ImportError):
            await create_stores(settings)
