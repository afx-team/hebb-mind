"""Ingestion data types — shared across detector, formats, and normalizer."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Format(str, Enum):
    """Supported conversation input formats."""

    CLAUDE_CODE_JSONL = "claude_code"
    CHATGPT_JSON = "chatgpt"
    PLAIN_TEXT = "plain"


class NormalizedTurn(BaseModel):
    """A single normalized conversation turn."""

    role: str = Field(description="'user' | 'assistant' | 'system' | 'tool'")
    content: str = Field(description="Cleaned text content")
    session_id: str | None = Field(default=None)
    turn_index: int = Field(default=0, ge=0)
    timestamp: str | None = Field(default=None)


class IngestResult(BaseModel):
    """Result of normalizing a conversation input."""

    format_detected: str
    turns: list[NormalizedTurn]
    turn_count: int
    warnings: list[str] = Field(default_factory=list)
