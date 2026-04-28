"""Tests for SQLite storage layer."""

import pytest

from hippocampus.constants import PartitionType
from hippocampus.models.memory import MemoryCreate, MemoryUpdate
from hippocampus.models.partition import PartitionCreate, PartitionUpdate


class TestPartitionStore:
    @pytest.mark.asyncio
    async def test_ensure_defaults(self, partition_store):
        partitions = await partition_store.list()
        ids = {p.id for p in partitions}
        assert PartitionType.HIPPOCAMPUS.value in ids
        assert PartitionType.SEMANTIC.value in ids
        assert PartitionType.EPISODIC.value in ids

    @pytest.mark.asyncio
    async def test_create_custom(self, partition_store):
        p = await partition_store.create(
            PartitionCreate(id="mem_custom", name="Custom", description="test"),
        )
        assert p.id == "mem_custom"
        assert p.name == "Custom"
        assert not p.is_system

    @pytest.mark.asyncio
    async def test_update(self, partition_store):
        p = await partition_store.update(
            PartitionType.SEMANTIC.value,
            PartitionUpdate(description="updated desc"),
        )
        assert p is not None
        assert p.description == "updated desc"

    @pytest.mark.asyncio
    async def test_cannot_delete_system(self, partition_store):
        result = await partition_store.delete(PartitionType.HIPPOCAMPUS.value)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_custom(self, partition_store):
        await partition_store.create(
            PartitionCreate(id="mem_temp", name="Temp"),
        )
        result = await partition_store.delete("mem_temp")
        assert result is True


class TestMemoryStore:
    @pytest.mark.asyncio
    async def test_create_and_get(self, memory_store):
        m = await memory_store.create(
            MemoryCreate(content="hello world", partition_id="mem_hippocampus"),
        )
        assert m.content == "hello world"

        fetched = await memory_store.get(m.id)
        assert fetched is not None
        assert fetched.content == "hello world"

    @pytest.mark.asyncio
    async def test_list_with_filter(self, memory_store):
        await memory_store.create(MemoryCreate(content="a", partition_id="mem_hippocampus"))
        await memory_store.create(MemoryCreate(content="b", partition_id="mem_semantic"))

        memories, total = await memory_store.list(partition_id="mem_hippocampus")
        assert total == 1
        assert memories[0].content == "a"

    @pytest.mark.asyncio
    async def test_update(self, memory_store):
        m = await memory_store.create(MemoryCreate(content="original"))
        updated = await memory_store.update(m.id, MemoryUpdate(content="modified"))
        assert updated is not None
        assert updated.content == "modified"

    @pytest.mark.asyncio
    async def test_delete(self, memory_store):
        m = await memory_store.create(MemoryCreate(content="to delete"))
        result = await memory_store.delete(m.id)
        assert result is True
        assert await memory_store.get(m.id) is None

    @pytest.mark.asyncio
    async def test_access_tracking(self, memory_store):
        m = await memory_store.create(MemoryCreate(content="track me"))
        await memory_store.update_access(m.id)
        await memory_store.update_access(m.id)

        fetched = await memory_store.get(m.id)
        assert fetched is not None
        assert fetched.access_count == 2

    @pytest.mark.asyncio
    async def test_get_by_partition(self, memory_store):
        await memory_store.create(MemoryCreate(content="a", partition_id="mem_hippocampus"))
        await memory_store.create(MemoryCreate(content="b", partition_id="mem_hippocampus"))
        await memory_store.create(MemoryCreate(content="c", partition_id="mem_semantic"))

        hippocampus = await memory_store.get_by_partition("mem_hippocampus")
        assert len(hippocampus) == 2
