"""Memory retrieval scoring — recency + importance + relevance."""

from __future__ import annotations

import math
from datetime import datetime, timezone


def compute_recency_score(
    last_accessed_at: datetime,
    now: datetime | None = None,
    decay_factor: float = 0.99,
) -> float:
    """Exponential decay based on hours since last access."""
    now = now or datetime.now(timezone.utc)
    hours = (now - last_accessed_at).total_seconds() / 3600.0
    return math.pow(decay_factor, max(hours, 0))


def compute_importance_score(importance: float) -> float:
    """Normalize importance (0-10) to [0, 1] range."""
    return min(max(importance / 10.0, 0.0), 1.0)


def compute_composite_score(
    recency: float,
    importance: float,
    relevance: float,
    weight_recency: float = 1.0,
    weight_importance: float = 1.0,
    weight_relevance: float = 1.0,
) -> float:
    """Weighted composite score, normalized to [0, 1]."""
    total_weight = weight_recency + weight_importance + weight_relevance
    if total_weight == 0:
        return 0.0
    return (weight_recency * recency + weight_importance * importance + weight_relevance * relevance) / total_weight
