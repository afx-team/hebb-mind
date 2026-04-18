"""Admin endpoints — manual triggers and stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hippocampus.config.settings import Settings
from hippocampus.embedding.base import EmbeddingProvider
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.scheduler.consolidation_job import run_consolidation
from hippocampus.scheduler.manager import SchedulerManager
from hippocampus.server.dependencies import (
    get_embedder,
    get_knowledge_graph,
    get_memory_store,
    get_partition_store,
    get_scheduler,
    get_settings,
)
from hippocampus.storage.base import MemoryStore, PartitionStore

router = APIRouter()


@router.post("/consolidate")
async def trigger_consolidation(
    memory_store: MemoryStore = Depends(get_memory_store),
    partition_store: PartitionStore = Depends(get_partition_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
    embedder: EmbeddingProvider = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
):
    results = await run_consolidation(
        memory_store=memory_store,
        partition_store=partition_store,
        knowledge_graph=kg,
        embedder=embedder,
        settings=settings,
    )
    return {
        "processed": len(results),
        "succeeded": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
    }


@router.post("/forget")
async def trigger_forgetting(
    memory_store: MemoryStore = Depends(get_memory_store),
):
    deleted = await memory_store.delete_expired()
    return {"deleted": deleted}


@router.get("/stats")
async def get_stats(
    memory_store: MemoryStore = Depends(get_memory_store),
    partition_store: PartitionStore = Depends(get_partition_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
    scheduler: SchedulerManager = Depends(get_scheduler),
):
    partitions = await partition_store.list()
    partition_stats = [
        {"id": p.id, "name": p.name, "memory_count": p.memory_count, "enabled": p.enabled}
        for p in partitions
    ]
    graph_state = kg.export()
    return {
        "partitions": partition_stats,
        "total_memories": sum(p.memory_count for p in partitions),
        "graph": {
            "tag_count": len(graph_state.nodes),
            "edge_count": len(graph_state.edges),
        },
        "scheduler": scheduler.get_status(),
    }
