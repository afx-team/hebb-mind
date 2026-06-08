"""Single cross-store deletion invariant.

A memory lives in four stores: the SQLite ``memories`` table, the vec0 embedding
table, the FTS5 index, and the knowledge-graph JSON. ``MemoryStore.delete``
covers the three SQL tables; the knowledge graph is a fourth store outside that
contract. ``purge_memory`` is the one definition of "a memory was deleted" so
every call site keeps all four in sync instead of re-implementing — and
occasionally forgetting — the graph cleanup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hebb.graph.knowledge_graph import KnowledgeGraph
    from hebb.storage.base import MemoryStore


async def purge_memory(
    store: MemoryStore,
    kg: KnowledgeGraph,
    memory_id: str,
    *,
    save: bool = True,
) -> bool:
    """Delete a memory from every store: SQL rows, vec0, FTS5, and the graph.

    Args:
        store: Memory store; deletes ``memories`` + ``memory_embeddings`` +
            ``memory_fts``.
        kg: Knowledge graph; strips the id from every tag node and prunes nodes
            left with no memories.
        memory_id: The memory to remove.
        save: Persist the graph to disk after the removal. Pass ``False`` in
            batch loops and call ``kg.save()`` once at the end to avoid an
            O(nodes) file write per memory.

    Returns:
        ``True`` if the SQL row existed and was deleted, ``False`` otherwise.
        Graph cleanup runs regardless of the row's existence, so a pre-existing
        orphan referencing ``memory_id`` is still swept.
    """
    deleted = await store.delete(memory_id)
    kg.remove_memory_from_tags(memory_id)
    if save:
        kg.save()
    return deleted
