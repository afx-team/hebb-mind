"""Per-partition forgetting parameter resolution.

Covers ``resolve_forgetting_params`` — the single point that maps a partition id
to its effective parameters via override → region default → global, shared by the
scheduled sweep and the manual ``POST /forget``.
"""

from __future__ import annotations

from hebb.config.settings import PartitionForgettingOverride, Settings
from hebb.scheduler.forgetting_job import resolve_forgetting_params

_GLOBALS = dict(half_life_days=60.0, k_importance=2.0, k_access=1.5, forget_threshold=0.3)


def _settings(**overrides: PartitionForgettingOverride) -> Settings:
    return Settings(**_GLOBALS, forgetting_overrides=dict(overrides))


def test_no_override_inherits_global() -> None:
    # A user partition (not a built-in region) falls back to the global defaults.
    params = resolve_forgetting_params("mem_facts", _settings())
    assert params.half_life_days == 60.0
    assert params.k_importance == 2.0
    assert params.k_access == 1.5
    assert params.threshold == 0.3
    assert params.enabled is True


def test_region_default_when_no_override() -> None:
    # A built-in region with no override inherits its REGION_FORGET_DEFAULTS entry.
    params = resolve_forgetting_params("mem_episodic", _settings())
    assert params.half_life_days == 30.0
    assert params.k_importance == 1.0
    assert params.k_access == 1.0


def test_full_override_wins() -> None:
    s = _settings(
        mem_episodic=PartitionForgettingOverride(
            half_life_days=720.0, k_importance=5.0, k_access=2.0, threshold=0.5, enabled=True
        )
    )
    params = resolve_forgetting_params("mem_episodic", s)
    assert params.half_life_days == 720.0
    assert params.k_importance == 5.0
    assert params.k_access == 2.0
    assert params.threshold == 0.5


def test_partial_override_inherits_region_then_global() -> None:
    # Override only half_life on a region; the rest fall back to the region default.
    s = _settings(mem_episodic=PartitionForgettingOverride(half_life_days=720.0))
    params = resolve_forgetting_params("mem_episodic", s)
    assert params.half_life_days == 720.0
    assert params.k_importance == 1.0  # episodic region default
    assert params.threshold == 0.3


def test_zero_coefficient_is_a_real_override_not_inherit() -> None:
    # k_access=0 (access never extends) is a valid override, not "unset".
    s = _settings(mem_facts=PartitionForgettingOverride(k_access=0.0))
    params = resolve_forgetting_params("mem_facts", s)
    assert params.k_access == 0.0
    assert params.half_life_days == 60.0


def test_disabled_override() -> None:
    s = _settings(mem_scratch=PartitionForgettingOverride(enabled=False))
    params = resolve_forgetting_params("mem_scratch", s)
    assert params.enabled is False
    # params still resolve (callers gate on .enabled before using them).
    assert params.half_life_days == 60.0


def test_override_for_other_partition_does_not_leak() -> None:
    s = _settings(mem_facts=PartitionForgettingOverride(half_life_days=720.0, enabled=False))
    other = resolve_forgetting_params("mem_notes", s)
    assert other.half_life_days == 60.0
    assert other.enabled is True
