"""Tests for the cross-store ``purge_memory`` invariant.

A memory lives in the SQLite rows, vec0, FTS5, and the knowledge-graph JSON.
``purge_memory`` is the single definition of "deleted" that keeps all four in
sync. These tests assert SQL and graph agree after a purge.
"""

from __future__ import annotations

import pytest

from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import MemoryCreate
from hebb.storage.purge import purge_memory


@pytest.mark.asyncio
async def test_purge_removes_sql_row_and_graph_node(memory_store, shared_lock, tmp_path):
    kg = KnowledgeGraph(tmp_path / "kg.json", lock=shared_lock)
    mem = await memory_store.create(
        MemoryCreate(content="graphed memory", partition_id="mem_hippocampus")
    )
    kg.update_from_tags(["alpha"], mem.id)
    assert kg.get_tag("alpha") is not None

    deleted = await purge_memory(memory_store, kg, mem.id)

    assert deleted is True
    assert await memory_store.get(mem.id) is None
    # The tag had only this memory, so it is pruned — SQL and graph agree.
    assert kg.get_tag("alpha") is None


@pytest.mark.asyncio
async def test_purge_cleans_graph_even_when_row_absent(memory_store, shared_lock, tmp_path):
    """Graph cleanup runs regardless of the row's existence, so a stale
    reference is swept rather than left dangling."""
    kg = KnowledgeGraph(tmp_path / "kg.json", lock=shared_lock)
    kg.update_from_tags(["ghost"], "missing-id")
    assert kg.get_tag("ghost") is not None

    deleted = await purge_memory(memory_store, kg, "missing-id")

    assert deleted is False  # the row never existed
    assert kg.get_tag("ghost") is None  # but the dangling reference is gone
