"""Memory data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class MemoryCreate(BaseModel):
    """Request body for creating a memory."""

    content: str = Field(..., min_length=1, max_length=10000)
    partition_id: str = Field(default="mem_hippocampus")
    importance_score: float = Field(default=5.0, ge=0.0, le=10.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    source: str | None = Field(default=None, description="Origin: 'api', 'agent', 'consolidation'")


class MemoryUpdate(BaseModel):
    """Request body for updating a memory."""

    content: str | None = None
    importance_score: float | None = Field(default=None, ge=0.0, le=10.0)
    tags: list[str] | None = None
    metadata: dict[str, str] | None = None


class Memory(BaseModel):
    """Full memory record."""

    id: str = Field(default_factory=_uuid)
    partition_id: str = "mem_hippocampus"
    content: str = ""
    importance_score: float = 5.0
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
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


class MemorySearchResult(BaseModel):
    """A single search result with scoring breakdown."""

    memory: Memory
    score: float
    recency_score: float
    importance_score_normalized: float
    relevance_score: float


class SearchResponse(BaseModel):
    """Full search response with main results and graph-expanded related memories."""

    results: list[MemorySearchResult]
    related: list[Memory] = Field(default_factory=list)
