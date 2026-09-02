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

    When the store exposes a ``_write_lock`` (SQLite backend, Issue #36), the
    SQL delete and the graph mutation are performed inside a single critical
    section so they form one crash-consistent unit. For backends without a
    shared lock (PostgreSQL pool), the SQL delete runs independently and the
    graph mutation is guarded by ``kg.lock``.

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
    # SQLite backend exposes a process-level ``_write_lock`` that, in the
    # production wiring (api.py / app.py), is the same object as ``kg.lock``.
    # Acquire ``kg.lock`` explicitly so the SQL delete and the graph mutation
    # always form one critical section — even when an SDK / test caller wires a
    # different lock into the store. ``asyncio.Lock`` is non-reentrant, so when
    # the two locks are identical we take it only once (a second ``async with``
    # on the same object would deadlock).
    shared_lock = getattr(store, "_write_lock", None)
    if shared_lock is not None and hasattr(store, "_delete_impl"):
        # ``_delete_impl`` already COMMITTED before we touch the graph, so the SQL
        # rollback path can never diverge the in-memory graph. The narrow commit
        # → save() crash window may leave a KG→SQL orphan that ``reconcile()``
        # sweeps on the next start (KG→SQL orphans are self-healing; SQL→KG lost
        # forward refs are not, so ordering the graph mutation after the commit is
        # the safer trade-off here — Issue #36; Gemini/Copilot review).
        if shared_lock is kg.lock:
            async with shared_lock:
                deleted = await store._delete_impl(memory_id)
                kg.remove_memory_from_tags(memory_id)
                if save:
                    kg.save()
        else:
            # SDK / test wiring where the store's write lock differs from kg.lock:
            # acquire both so a concurrent KG operation cannot race the mutation.
            # Always acquire in the same documented order (store lock → kg lock)
            # to avoid lock-ordering deadlocks with other paths in this codebase.
            async with shared_lock, kg.lock:
                deleted = await store._delete_impl(memory_id)
                kg.remove_memory_from_tags(memory_id)
                if save:
                    kg.save()
    else:
        # PostgreSQL pool backend: no shared lock; KG guarded by its own lock.
        deleted = await store.delete(memory_id)
        async with kg.lock:
            kg.remove_memory_from_tags(memory_id)
            if save:
                kg.save()
    return deleted
