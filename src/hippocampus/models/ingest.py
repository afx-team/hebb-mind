"""Ingestion request/response models for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request body for conversation ingestion."""

    content: str = Field(..., min_length=1, max_length=500000, description="Raw conversation data")
    format_hint: str | None = Field(
        default=None,
        description="Format override: 'claude_code', 'chatgpt', 'plain'",
    )
    partition_id: str = Field(default="mem_hippocampus")
    importance_score: float = Field(default=5.0, ge=0.0, le=10.0)
    source: str | None = Field(default="ingest")


class IngestResponse(BaseModel):
    """Response from conversation ingestion."""

    format_detected: str
    turns_parsed: int
    memories_created: int
    warnings: list[str] = Field(default_factory=list)
