"""Common response models."""

from __future__ import annotations

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    """Paginated list response."""

    items: list[T]
    total: int
    offset: int
    limit: int


class APIResponse[T](BaseModel):
    """Generic API response wrapper."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    """Error response."""

    success: bool = False
    error: str
    detail: str | None = None
