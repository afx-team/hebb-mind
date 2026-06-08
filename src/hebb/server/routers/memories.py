"""Memory CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.ingest.normalizer import normalize
from hebb.models.common import PaginatedResponse
from hebb.models.ingest import IngestRequest, IngestResponse
from hebb.models.memory import Memory, MemoryCreate, MemoryMetadata, MemoryUpdate
from hebb.server.dependencies import (
    get_embedder,
    get_knowledge_graph,
    get_memory_store,
)
from hebb.storage.base import MemoryStore
from hebb.storage.purge import purge_memory

router = APIRouter()


@router.get("/memories", response_model=PaginatedResponse[Memory])
async def list_memories(
    partition_id: str | None = Query(default=None),
    tags: str | None = Query(default=None, description="Comma-separated tags"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    store: MemoryStore = Depends(get_memory_store),
) -> PaginatedResponse[Memory]:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    memories, total = await store.list(
        partition_id=partition_id,
        tags=tag_list,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(items=memories, total=total, offset=offset, limit=limit)


@router.get("/memories/{memory_id}", response_model=Memory)
async def get_memory(
    memory_id: str,
    store: MemoryStore = Depends(get_memory_store),
) -> Memory:
    memory = await store.get(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Track access
    await store.update_access(memory_id)
    return memory


@router.post("/memories", response_model=Memory, status_code=201)
async def create_memory(
    data: MemoryCreate,
    store: MemoryStore = Depends(get_memory_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> Memory:
    embedding = await embedder.embed(data.content)
    return await store.create(data, embedding=embedding)


@router.post("/memories/batch", response_model=list[Memory], status_code=201)
async def create_memories_batch(
    items: list[MemoryCreate],
    store: MemoryStore = Depends(get_memory_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> list[Memory]:
    results: list[Memory] = []
    texts = [item.content for item in items]
    embeddings = await embedder.embed_batch(texts)
    for item, emb in zip(items, embeddings):
        memory = await store.create(item, embedding=emb)
        results.append(memory)
    return results


@router.patch("/memories/{memory_id}", response_model=Memory)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    store: MemoryStore = Depends(get_memory_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> Memory:
    memory = await store.update(memory_id, data)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    # Re-embed if content changed
    if data.content is not None:
        embedding = await embedder.embed(data.content)
        await store.update_embedding(memory_id, embedding)
    return memory


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    store: MemoryStore = Depends(get_memory_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
):
    deleted = await purge_memory(store, kg, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")


@router.post("/ingest", response_model=IngestResponse, status_code=201)
async def ingest_conversation(
    data: IngestRequest,
    store: MemoryStore = Depends(get_memory_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> IngestResponse:
    """Ingest a conversation export: auto-detect format, normalize, and store as memories."""
    result = normalize(data.content, format_hint=data.format_hint)

    items: list[MemoryCreate] = []
    for turn in result.turns:
        formatted = f"[{turn.role}]: {turn.content}"
        # Carry the parsed timestamp into metadata (extra field) — the
        # searcher's temporal_boost reads metadata.timestamp, so dropping it
        # here made date-anchored queries blind to ingested turns.
        meta_kwargs: dict[str, object] = {
            "session_id": turn.session_id,
            "turn": turn.turn_index,
        }
        if turn.timestamp:
            meta_kwargs["timestamp"] = turn.timestamp
        metadata = MemoryMetadata.model_validate(meta_kwargs)
        items.append(
            MemoryCreate(
                content=formatted[:10000],
                partition_id=data.partition_id,
                importance_score=data.importance_score,
                metadata=metadata,
                source=data.source,
            )
        )

    # Batch embed and store
    if items:
        texts = [item.content for item in items]
        embeddings = await embedder.embed_batch(texts)
        for item, emb in zip(items, embeddings):
            await store.create(item, embedding=emb)

    return IngestResponse(
        format_detected=result.format_detected,
        turns_parsed=result.turn_count,
        memories_created=len(items),
        warnings=result.warnings,
    )
