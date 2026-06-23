"""Forgetting job — retention-score model: compute a memory's retained lifetime
and delete it once its retention would have decayed below the threshold.

Model (a faithful Ebbinghaus forgetting curve, mirrored client-side in
``static/js/lib/forgetting-math.js``)::

    eff_half_life = half_life_days · (1 + k_importance·(importance/10) + k_access·(access_count/10))
    retention(idle_days) = exp(−idle_days / eff_half_life)
    forget when retention < threshold
        ⇔ idle_days > eff_half_life · ln(1/threshold)

``importance`` (0–10) and ``access_count`` (uncapped) stretch the half-life
linearly; idle time since last access decays retention. An ``importance`` of 0
simply contributes no boost (it is NOT a delete signal). A global floor
(``min_retention_days``) guards against pathological settings collapsing to
instant deletion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from hebb.config.settings import Settings
from hebb.constants import PartitionType
from hebb.models.memory import Memory

# Hard floor (days) on a memory's retained lifetime. Mirrors the default of
# ``Settings.forget_min_retention_days``; callers pass the configured value.
DEFAULT_MIN_RETENTION_DAYS = 1.0

# Per-region forgetting defaults for the built-in cortical partitions. A field
# absent here (or a region absent here) falls back to the global ``Settings``
# value. HIPPOCAMPUS is never swept, so it has no entry.
REGION_FORGET_DEFAULTS: dict[str, dict[str, float]] = {
    PartitionType.EPISODIC.value: {"half_life_days": 30.0, "k_importance": 1.0, "k_access": 1.0, "threshold": 0.3},
    PartitionType.SEMANTIC.value: {"half_life_days": 90.0, "k_importance": 3.0, "k_access": 1.5, "threshold": 0.3},
    PartitionType.PROCEDURAL.value: {"half_life_days": 90.0, "k_importance": 3.0, "k_access": 1.5, "threshold": 0.3},
    PartitionType.PREFERENCE.value: {"half_life_days": 180.0, "k_importance": 4.0, "k_access": 1.5, "threshold": 0.3},
}


def eff_half_life_days(
    half_life_days: float,
    k_importance: float,
    k_access: float,
    importance_score: float,
    access_count: int,
) -> float:
    """Effective half-life (days) for a memory.

    The base ``half_life_days`` is stretched linearly by importance and access::

        eff = half_life_days · (1 + k_importance·(importance/10) + k_access·(access_count/10))

    Args:
        half_life_days: Base half-life in days for a neutral memory.
        k_importance: Linear weight on normalized importance (importance/10).
        k_access: Linear weight on normalized access count (access_count/10).
        importance_score: Importance in [0, 10]; 0 contributes no boost.
        access_count: Number of times the memory has been accessed (uncapped).

    Returns:
        The effective half-life in days (>= ``half_life_days``).
    """
    return half_life_days * (1.0 + k_importance * (importance_score / 10.0) + k_access * (access_count / 10.0))


def retention(eff_half_life_days_value: float, idle_days: float) -> float:
    """Retention in [0, 1] after ``idle_days`` of inactivity: ``exp(−idle/eff_hl)``."""
    if eff_half_life_days_value <= 0:
        return 0.0
    return math.exp(-max(idle_days, 0.0) / eff_half_life_days_value)


def forget_idle_days(
    eff_half_life_days_value: float,
    threshold: float,
    min_retention_days: float = DEFAULT_MIN_RETENTION_DAYS,
) -> float:
    """Idle days at which retention drops below ``threshold`` (floored).

    ``retention(idle) = threshold`` ⇔ ``idle = eff_half_life · ln(1/threshold)``;
    the result is floored at ``min_retention_days``.
    """
    idle = eff_half_life_days_value * math.log(1.0 / threshold)
    return max(idle, min_retention_days)


def compute_expires_at(
    memory: Memory,
    half_life_days: float,
    k_importance: float,
    k_access: float,
    threshold: float,
    min_retention_days: float = DEFAULT_MIN_RETENTION_DAYS,
) -> datetime:
    """Compute the expiration datetime for a memory under the retention model.

    The memory is considered expired once its retention (decaying from its last
    access) would fall below ``threshold`` — i.e. at
    ``last_accessed_at + eff_half_life · ln(1/threshold)``, floored at
    ``min_retention_days``.

    Args:
        memory: The memory whose expiry to compute.
        half_life_days: Base half-life in days.
        k_importance: Linear weight on normalized importance.
        k_access: Linear weight on normalized access count.
        threshold: Retention level below which the memory is forgotten, in (0, 1).
        min_retention_days: Hard floor (days) on the retained lifetime.

    Returns:
        The UTC datetime at which the memory should be considered expired.
    """
    eff = eff_half_life_days(half_life_days, k_importance, k_access, memory.importance_score, memory.access_count)
    idle = forget_idle_days(eff, threshold, min_retention_days)
    return memory.last_accessed_at + timedelta(days=idle)


@dataclass(frozen=True)
class EffectiveForgettingParams:
    """The forgetting parameters in effect for one partition."""

    half_life_days: float
    k_importance: float
    k_access: float
    threshold: float
    enabled: bool


def resolve_forgetting_params(partition_id: str, settings: Settings) -> EffectiveForgettingParams:
    """Resolve the effective forgetting parameters for a partition.

    Resolution order, per field: per-partition override (in
    ``settings.forgetting_overrides``) → built-in region default
    (``REGION_FORGET_DEFAULTS``) → global ``Settings`` value. An override entry
    with ``enabled=False`` opts the partition out of the sweep entirely.

    This is the single resolution point shared by the scheduled sweep
    (:meth:`SchedulerManager._run_forgetting`) and the manual ``POST /forget``
    endpoint so the two can never drift.

    Args:
        partition_id: The partition whose policy to resolve.
        settings: Global settings holding the defaults and the overrides map.

    Returns:
        The resolved half-life, importance/access weights, threshold, and enabled.
    """
    override = settings.forgetting_overrides.get(partition_id)
    region = REGION_FORGET_DEFAULTS.get(partition_id)

    def pick(field: str, global_default: float) -> float:
        if override is not None:
            value = getattr(override, field)
            if value is not None:
                return float(value)
        if region is not None and field in region:
            return region[field]
        return global_default

    return EffectiveForgettingParams(
        half_life_days=pick("half_life_days", settings.half_life_days),
        k_importance=pick("k_importance", settings.k_importance),
        k_access=pick("k_access", settings.k_access),
        threshold=pick("threshold", settings.forget_threshold),
        enabled=override.enabled if override is not None else True,
    )


def resolve_inherited_params(partition_id: str, settings: Settings) -> EffectiveForgettingParams:
    """Region/global defaults for a partition, IGNORING any override.

    Used by the console tuner to show what each field falls back to when its
    override is cleared (the "inherit" baseline). ``enabled`` is always True.
    """
    region = REGION_FORGET_DEFAULTS.get(partition_id)

    def pick(field: str, global_default: float) -> float:
        if region is not None and field in region:
            return region[field]
        return global_default

    return EffectiveForgettingParams(
        half_life_days=pick("half_life_days", settings.half_life_days),
        k_importance=pick("k_importance", settings.k_importance),
        k_access=pick("k_access", settings.k_access),
        threshold=pick("threshold", settings.forget_threshold),
        enabled=True,
    )
