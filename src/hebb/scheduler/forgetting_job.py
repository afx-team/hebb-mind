"""Forgetting job — computes dynamic TTL and deletes expired memories."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from hebb.models.memory import Memory

# Minimum TTL floor (hours): a memory is never assigned a TTL below this, so a
# legitimately-stored memory can never collapse to "already expired" and be
# deleted on the very next sweep. Roughly one day of grace at the low end.
MIN_TTL_HOURS = 24.0

# Neutral importance midpoint. ``importance_score`` is in [0, 10]; a score of 0
# is a valid value (LLM / consolidation / ``MemoryCreate(ge=0.0)`` all permit
# it) and must NOT be read as "delete me immediately". Treat 0 as the neutral
# midpoint so the importance weight is 1.0 instead of 0.0.
NEUTRAL_IMPORTANCE = 5.0

# Grace TTL (hours) for brand-new memories (``access_count == 0``). A memory
# that has never been recalled still deserves at least one full forgetting
# interval before it can be deleted, otherwise a low-importance write could be
# swept before anything ever has a chance to access it.
NEW_MEMORY_GRACE_HOURS = 168.0


def compute_ttl_hours(
    last_accessed_at: datetime,
    access_count: int,
    importance_score: float,
    base_ttl_hours: float,
    decay_factor: float,
    now: datetime | None = None,
) -> float:
    """Compute the dynamic time-to-live (in hours) for a memory.

    Dynamic TTL formula::

        TTL = base_ttl * (1 + log(access_count)) * (importance / 5.0)
              * exp(-decay * days_since_access)

    Higher ``access_count`` and ``importance_score`` extend the TTL; more time
    since the last access shrinks it (exponential decay). The result is clamped
    to ``MIN_TTL_HOURS`` so a memory can never be assigned a TTL of 0 and be
    deleted on the next sweep. An ``importance_score`` of 0 is treated as the
    neutral midpoint (5.0) rather than "expire immediately".

    Args:
        last_accessed_at: Timestamp of the memory's most recent access.
        access_count: Number of times the memory has been accessed.
        importance_score: Importance in [0, 10]; 0 is treated as neutral (5.0).
        base_ttl_hours: Baseline TTL in hours for a neutral memory.
        decay_factor: Exponential decay rate per day since last access.
        now: Reference "now"; defaults to the current UTC time.

    Returns:
        TTL in hours, never below ``MIN_TTL_HOURS``.
    """
    now = now or datetime.now(timezone.utc)
    days_since = (now - last_accessed_at).total_seconds() / 86400.0
    # importance == 0 is a valid neutral value, not a delete signal.
    effective_importance = importance_score if importance_score > 0 else NEUTRAL_IMPORTANCE
    importance_weight = effective_importance / 5.0
    ttl = (
        base_ttl_hours
        * (1 + math.log(max(access_count, 1)))
        * importance_weight
        * math.exp(-decay_factor * max(days_since, 0))
    )
    return max(ttl, MIN_TTL_HOURS)


def compute_expires_at(memory: Memory, base_ttl_hours: float, decay_factor: float) -> datetime:
    """Compute the expiration datetime for a memory.

    Brand-new memories (``access_count == 0``) are given a grace TTL of at least
    ``NEW_MEMORY_GRACE_HOURS`` measured from creation, so a freshly written
    memory is never deleted within one forgetting interval of being stored.

    Args:
        memory: The memory whose expiry to compute.
        base_ttl_hours: Baseline TTL in hours for a neutral memory.
        decay_factor: Exponential decay rate per day since last access.

    Returns:
        The UTC datetime at which the memory should be considered expired.
    """
    ttl = compute_ttl_hours(
        last_accessed_at=memory.last_accessed_at,
        access_count=memory.access_count,
        importance_score=memory.importance_score,
        base_ttl_hours=base_ttl_hours,
        decay_factor=decay_factor,
    )
    expires_at = memory.last_accessed_at + timedelta(hours=ttl)

    # New, never-accessed memories get a creation-anchored grace window so they
    # survive at least one forgetting interval after being written.
    if memory.access_count == 0:
        grace_expiry = memory.created_at + timedelta(hours=NEW_MEMORY_GRACE_HOURS)
        expires_at = max(expires_at, grace_expiry)

    return expires_at
