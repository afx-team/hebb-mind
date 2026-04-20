"""Common response models."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T]
    total: int
    offset: int
    limit: int


class APIResponse(BaseModel, Generic[T]):
    """Generic API response wrapper."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response."""

    success: bool = False
    error: str
    detail: str | None = None