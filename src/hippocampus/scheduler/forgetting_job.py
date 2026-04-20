"""Forgetting job — computes dynamic TTL and deletes expired memories."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from hippocampus.models.memory import Memory


def compute_ttl_hours(
    last_accessed_at: datetime,
    access_count: int,
    importance_score: float,
    base_ttl_hours: float,
    decay_factor: float,
    now: datetime | None = None,
) -> float:
    """
    Dynamic TTL formula:
    TTL = base_ttl * (1 + log(access_count)) * (importance / 5.0) * exp(-decay * days_since_access)

    Higher access_count and importance -> longer TTL.
    More time since last access -> shorter TTL (exponential decay).
    """
    now = now or datetime.now(datetime.UTC)
    days_since = (now - last_accessed_at).total_seconds() / 86400.0
    importance_weight = importance_score / 5.0
    ttl = (
        base_ttl_hours
        * (1 + math.log(max(access_count, 1)))
        * importance_weight
        * math.exp(-decay_factor * max(days_since, 0))
    )
    return max(ttl, 0.0)


def compute_expires_at(memory: Memory, base_ttl_hours: float, decay_factor: float) -> datetime:
    """Compute the expiration datetime for a memory."""
    ttl = compute_ttl_hours(
        last_accessed_at=memory.last_accessed_at,
        access_count=memory.access_count,
        importance_score=memory.importance_score,
        base_ttl_hours=base_ttl_hours,
        decay_factor=decay_factor,
    )
    return memory.last_accessed_at + timedelta(hours=ttl)
