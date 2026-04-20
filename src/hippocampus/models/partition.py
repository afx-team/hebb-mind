"""Partition data models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PartitionCreate(BaseModel):
    """Request body for creating a partition."""

    id: str = Field(..., pattern=r"^mem_[a-z0-9_]+$", min_length=5, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="")
    enabled: bool = Field(default=True)


class PartitionUpdate(BaseModel):
    """Request body for updating a partition."""

    name: str | None = None
    description: str | None = None
    enabled: bool | None = None


class Partition(BaseModel):
    """Full partition record."""

    id: str
    name: str
    description: str = ""
    enabled: bool = True
    is_system: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.UTC))
    memory_count: int = 0

    model_config = {"from_attributes": True}
