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
    get_partition_store,
)
from hebb.storage.base import MemoryStore, PartitionStore
from hebb.storage.purge import purge_memory

router = APIRouter()


async def _require_partition(partitions: PartitionStore, partition_id: str) -> None:
    """Reject writes targeting a partition that does not exist.

    Without this guard a memory would be inserted with a dangling
    ``partition_id`` — the row persists but never surfaces in any
    partition-scoped list/search, i.e. a silent write-then-lose.

    Args:
        partitions: Partition store used to resolve ``partition_id``.
        partition_id: Target partition for the pending write.

    Raises:
        HTTPException: 404 if ``partition_id`` does not exist.
    """
    if await partitions.get(partition_id) is None:
        raise HTTPException(status_code=404, detail=f"Partition not found: {partition_id}")


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
    partitions: PartitionStore = Depends(get_partition_store),
) -> Memory:
    await _require_partition(partitions, data.partition_id)
    embedding = await embedder.embed(data.content)
    return await store.create(data, embedding=embedding)


@router.post("/memories/batch", response_model=list[Memory], status_code=201)
async def create_memories_batch(
    items: list[MemoryCreate],
    store: MemoryStore = Depends(get_memory_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
    partitions: PartitionStore = Depends(get_partition_store),
) -> list[Memory]:
    for partition_id in {item.partition_id for item in items}:
        await _require_partition(partitions, partition_id)
    results: list[Memory] = []
    texts = [item.content for item in items]
    embeddings = await embedder.embed_batch(texts)
    # An embedder that drops/merges rows would otherwise misalign content to
    # vectors via zip's silent truncation; fail loud and count only rows we
    # actually inserted rather than len(items). (write F4)
    if len(embeddings) != len(items):
        raise HTTPException(
            status_code=502,
            detail=f"Embedder returned {len(embeddings)} vectors for {len(items)} inputs",
        )
    for item, emb in zip(items, embeddings, strict=True):
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
    # Reject an explicit empty/whitespace content edit: overwriting + re-embedding
    # a memory with a blank body silently destroys it. An omitted content field
    # (None) is still a valid "no change". (INT-5)
    if data.content is not None and not data.content.strip():
        raise HTTPException(status_code=422, detail="content must not be empty or whitespace")
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
    partitions: PartitionStore = Depends(get_partition_store),
) -> IngestResponse:
    """Ingest a conversation export: auto-detect format, normalize, and store as memories."""
    await _require_partition(partitions, data.partition_id)
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

    # Batch embed and store. Count what we actually insert — an embedder that
    # returns fewer vectors than turns must fail loud, not silently drop the
    # tail (zip strict) and over-report memories_created. (write F4)
    memories_created = 0
    if items:
        texts = [item.content for item in items]
        embeddings = await embedder.embed_batch(texts)
        if len(embeddings) != len(items):
            raise HTTPException(
                status_code=502,
                detail=f"Embedder returned {len(embeddings)} vectors for {len(items)} inputs",
            )
        for item, emb in zip(items, embeddings, strict=True):
            await store.create(item, embedding=emb)
            memories_created += 1

    return IngestResponse(
        format_detected=result.format_detected,
        turns_parsed=result.turn_count,
        memories_created=memories_created,
        warnings=result.warnings,
    )
