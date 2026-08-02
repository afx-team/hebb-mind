"""Memory data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class MemoryMetadata(BaseModel):
    """Structured metadata with reserved fields and extensible extras.

    Reserved fields:
        session_id: Conversation/session identifier for grouping memories.
        turn: Turn index within a session (0-based).

    Any additional fields are accepted and stored as-is.
    """

    session_id: str | None = Field(default=None, description="Conversation or session ID")
    turn: int | None = Field(default=None, ge=0, description="Turn index within the session")

    model_config = {"extra": "allow"}


class MemoryCreate(BaseModel):
    """Request body for creating a memory."""

    content: str = Field(..., min_length=1, max_length=10000)
    partition_id: str = Field(default="mem_hippocampus")
    importance_score: float = Field(default=5.0, ge=0.0, le=10.0)
    tags: list[str] = Field(default_factory=list)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)
    source: str | None = Field(default=None, description="Origin: 'api', 'agent', 'consolidation'")


class MemoryUpdate(BaseModel):
    """Request body for updating a memory."""

    content: str | None = None
    importance_score: float | None = Field(default=None, ge=0.0, le=10.0)
    tags: list[str] | None = None
    metadata: MemoryMetadata | None = None


class Memory(BaseModel):
    """Full memory record."""

    id: str = Field(default_factory=_uuid)
    partition_id: str = "mem_hippocampus"
    content: str = ""
    importance_score: float = 5.0
    tags: list[str] = Field(default_factory=list)
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)
    source: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    last_accessed_at: datetime = Field(default_factory=_utcnow)
    access_count: int = 0
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class MemoryQuery(BaseModel):
    """Search query for memory retrieval."""

    query: str = Field(..., min_length=1)
    partition_ids: list[str] | None = None
    tags: list[str] | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    weight_recency: float = Field(default=1.0, ge=0.0)
    weight_importance: float = Field(default=1.0, ge=0.0)
    weight_relevance: float = Field(default=1.0, ge=0.0)
    # Relevance floor in [0, 1]: drop results whose final score is below this.
    # 0 means no filtering (the console default). The searcher clamps scores to
    # [0, 1] before this filter, so the floor lives on the same [0, 1] scale.
    min_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Drop results scoring below this floor (0-1); 0 = no filter"
    )
    # Strict recall surfaces (Claude Code hook, MCP) set this so the server
    # applies its configured ``recall_min_score`` floor without the caller
    # needing to know the value. Ignored when ``min_score`` is set explicitly.
    strict_recall: bool = Field(default=False, description="Apply the server's configured recall_min_score floor")
    # DEPRECATED: This field is retained only as an emergency rollback switch.
    # New code should use ``filter_score`` for composite-score filtering instead.
    # Original purpose: when ``min_score > 0`` and a reranker ran, the floor was
    # multiplied by this for reranked entries (sigmoid vs. composite scale).
    # The searcher reads this from the query; the router sets it when
    # ``strict_recall`` is active and the caller did not override it.
    rerank_floor_ratio: float = Field(
        default=0.625, ge=0.0, le=1.0,
        description="[DEPRECATED] Retained as emergency rollback only. Use filter_score instead. "
        "Original purpose: floor translation ratio for reranked entries "
        "(sigmoid vs. composite scale).",
    )
    # Composite-score filter: when set (>0), results with composite score below
    # this value are dropped. This replaces the old dual-scale filtering that
    # used rerank_floor_ratio to translate between sigmoid and composite scales.
    # The router sets this from settings.filter_score when strict_recall is
    # active and the caller did not override it.
    filter_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Composite-score filter threshold (0-1); 0 = no filter. "
        "When set, ignores rerank_floor_ratio and filters all results "
        "on the composite scale directly.",
    )
    # Context window expansion: when a top result has session_id+turn
    # metadata, also pull this many *adjacent* turns from the same
    # session and return them via SearchResponse.related. The hit memory
    # itself stays at its scored rank; the neighbours give the LLM the
    # surrounding dialog without polluting the ranking signal.
    prev_turns: int = Field(default=0, ge=0, le=20, description="Adjacent turns before each hit to include in related")
    next_turns: int = Field(default=0, ge=0, le=20, description="Adjacent turns after each hit to include in related")


class MemorySearchResult(BaseModel):
    """A single search result with scoring breakdown."""

    memory: Memory
    score: float
    recency_score: float
    importance_score_normalized: float
    relevance_score: float
    pre_rerank_score: float = Field(description="Composite score preserved before reranker overwrites score")


class SearchResponse(BaseModel):
    """Full search response with main results and graph-expanded related memories."""

    results: list[MemorySearchResult]
    related: list[Memory] = Field(default_factory=list)
