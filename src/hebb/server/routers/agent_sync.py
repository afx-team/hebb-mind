"""Agent session collection and synchronization endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from hebb.embedding.base import EmbeddingProvider
from hebb.integrations import session_sync
from hebb.models.memory import Memory, MemoryCreate
from hebb.server.dependencies import get_embedder, get_memory_store
from hebb.storage.base import MemoryStore

router = APIRouter()

AgentHost = Literal["codex", "claude_code"]
_UNKNOWN_HOST = "*"


class AgentSessionOut(BaseModel):
    id: str
    host: AgentHost
    path: str
    session_id: str
    project: str | None
    updated_at: float
    latest_timestamp: str | None
    turn_count: int
    synced_turns: int
    unsynced_turns: int


class AgentSyncRequest(BaseModel):
    host: AgentHost | None = None
    ids: list[str] = Field(default_factory=list, description="Opaque session ids returned by /agent-sync/sessions")
    limit: int | None = Field(default=None, ge=1, le=500)
    dry_run: bool = False


class AgentSyncItem(BaseModel):
    id: str
    host: AgentHost
    project: str | None
    path: str
    turns_found: int
    memories_created: int
    skipped_existing: int
    failed: int


class AgentSyncResponse(BaseModel):
    sessions_scanned: int
    turns_found: int
    memories_created: int
    skipped_existing: int
    failed: int
    dry_run: bool
    items: list[AgentSyncItem]


@router.get("/sessions", response_model=list[AgentSessionOut])
async def list_sessions(
    host: AgentHost | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    store: MemoryStore = Depends(get_memory_store),
) -> list[AgentSessionOut]:
    """List local Codex and Claude Code sessions with sync status."""
    sessions = session_sync.discover_sessions(host=host, limit=limit)
    existing = await _existing_turn_keys(store)
    return [_session_out(session, existing) for session in sessions]


@router.post("/sync", response_model=AgentSyncResponse)
async def sync_sessions(
    request: AgentSyncRequest,
    store: MemoryStore = Depends(get_memory_store),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> AgentSyncResponse:
    """Sync local Codex and Claude Code session turns into Hebb Mind."""
    sessions = session_sync.discover_sessions(host=request.host, limit=request.limit)
    if request.ids:
        wanted = set(request.ids)
        sessions = [session for session in sessions if session.id in wanted]

    existing = await _existing_turn_keys(store)
    items: list[AgentSyncItem] = []
    pending: list[tuple[session_sync.AgentSession, session_sync.AgentTurn, MemoryCreate]] = []

    for session in sessions:
        skipped = 0
        for turn in session.turns:
            if _has_existing(existing, session.host, session.session_id, turn.turn):
                skipped += 1
                continue
            pending.append((session, turn, session_sync.to_memory_create(session, turn)))
        items.append(
            AgentSyncItem(
                id=session.id,
                host=session.host,
                project=session.project,
                path=session.path,
                turns_found=session.turn_count,
                memories_created=0,
                skipped_existing=skipped,
                failed=0,
            )
        )

    if request.dry_run or not pending:
        return _response(items, dry_run=request.dry_run)

    embeddings = await embedder.embed_batch([memory.content for _, _, memory in pending])
    if len(embeddings) != len(pending):
        raise HTTPException(
            status_code=502,
            detail=f"Embedder returned {len(embeddings)} vectors for {len(pending)} imported turns",
        )

    item_by_id = {item.id: item for item in items}
    for (session, turn, memory), embedding in zip(pending, embeddings, strict=True):
        item = item_by_id[session.id]
        try:
            await store.create(memory, embedding=embedding)
        except Exception:
            item.failed += 1
            continue
        item.memories_created += 1
        existing.add(session_sync.turn_key(session.host, session.session_id, turn.turn))

    return _response(items, dry_run=False)


async def _existing_turn_keys(store: MemoryStore) -> set[tuple[str, str, int]]:
    memories = await store.get_by_partition(session_sync.HIPPOCAMPUS_PARTITION)
    keys: set[tuple[str, str, int]] = set()
    for memory in memories:
        meta = _metadata_dict(memory)
        session_id = meta.get("session_id")
        turn = meta.get("turn")
        if not isinstance(session_id, str) or not isinstance(turn, int):
            continue
        host = meta.get("host")
        keys.add(session_sync.turn_key(host if isinstance(host, str) else _UNKNOWN_HOST, session_id, turn))
    return keys


def _metadata_dict(memory: Memory) -> dict[str, object]:
    return memory.metadata.model_dump(exclude_none=True)


def _has_existing(keys: set[tuple[str, str, int]], host: str, session_id: str, turn: int) -> bool:
    return (
        session_sync.turn_key(host, session_id, turn) in keys
        or session_sync.turn_key(_UNKNOWN_HOST, session_id, turn) in keys
    )


def _session_out(session: session_sync.AgentSession, existing: set[tuple[str, str, int]]) -> AgentSessionOut:
    synced = sum(1 for turn in session.turns if _has_existing(existing, session.host, session.session_id, turn.turn))
    return AgentSessionOut(
        id=session.id,
        host=session.host,
        path=session.path,
        session_id=session.session_id,
        project=session.project,
        updated_at=session.updated_at,
        latest_timestamp=session.latest_timestamp,
        turn_count=session.turn_count,
        synced_turns=synced,
        unsynced_turns=max(session.turn_count - synced, 0),
    )


def _response(items: list[AgentSyncItem], *, dry_run: bool) -> AgentSyncResponse:
    return AgentSyncResponse(
        sessions_scanned=len(items),
        turns_found=sum(item.turns_found for item in items),
        memories_created=sum(item.memories_created for item in items),
        skipped_existing=sum(item.skipped_existing for item in items),
        failed=sum(item.failed for item in items),
        dry_run=dry_run,
        items=items,
    )
