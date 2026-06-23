"""Tests for the retention-score forgetting formula."""

from __future__ import annotations

import math

import pytest

from hebb.scheduler.forgetting_job import (
    DEFAULT_MIN_RETENTION_DAYS,
    eff_half_life_days,
    forget_idle_days,
    retention,
)


class TestForgettingFormula:
    def test_eff_half_life_baseline(self):
        # Neutral memory (importance 0, access 0) → just the base half-life.
        assert eff_half_life_days(60.0, 2.0, 1.5, 0.0, 0) == pytest.approx(60.0)

    def test_importance_extends_half_life(self):
        low = eff_half_life_days(60.0, 2.0, 1.5, 2.0, 1)
        high = eff_half_life_days(60.0, 2.0, 1.5, 9.0, 1)
        assert high > low

    def test_access_extends_half_life(self):
        low = eff_half_life_days(60.0, 2.0, 1.5, 5.0, 1)
        high = eff_half_life_days(60.0, 2.0, 1.5, 5.0, 100)
        assert high > low

    def test_access_is_uncapped(self):
        # access_count/10 is uncapped, so 100 accesses keep extending past 50.
        assert eff_half_life_days(60.0, 2.0, 1.5, 5.0, 100) > eff_half_life_days(60.0, 2.0, 1.5, 5.0, 50)

    def test_retention_decays_with_idle(self):
        eff = eff_half_life_days(60.0, 2.0, 1.5, 5.0, 1)
        assert retention(eff, 0) == pytest.approx(1.0)
        assert retention(eff, 10) > retention(eff, 30)
        # retention = exp(−idle/eff): 1/e at the characteristic time, 0.5 at eff·ln2.
        assert retention(eff, eff) == pytest.approx(math.exp(-1))
        assert retention(eff, eff * math.log(2)) == pytest.approx(0.5)

    def test_forget_idle_matches_threshold_crossing(self):
        eff = 60.0
        threshold = 0.3
        idle = forget_idle_days(eff, threshold)
        # By definition retention(idle) == threshold (above the floor).
        assert retention(eff, idle) == pytest.approx(threshold)
        assert idle == pytest.approx(eff * math.log(1 / threshold))

    def test_forget_idle_floored_at_min_retention(self):
        # A pathological tiny half-life / high threshold can't collapse below the floor.
        idle = forget_idle_days(0.1, 0.9, min_retention_days=DEFAULT_MIN_RETENTION_DAYS)
        assert idle == pytest.approx(DEFAULT_MIN_RETENTION_DAYS)

    def test_higher_threshold_forgets_sooner(self):
        eff = 60.0
        assert forget_idle_days(eff, 0.5) < forget_idle_days(eff, 0.2)
