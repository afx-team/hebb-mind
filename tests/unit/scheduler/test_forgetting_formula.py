"""Tests for forgetting mechanism."""

from datetime import datetime, timedelta, timezone

import pytest

from hebb.scheduler.forgetting_job import compute_ttl_hours


class TestForgettingFormula:
    def test_baseline_ttl(self):
        now = datetime.now(timezone.utc)
        ttl = compute_ttl_hours(
            last_accessed_at=now,
            access_count=1,
            importance_score=5.0,
            base_ttl_hours=168.0,
            decay_factor=0.693,
            now=now,
        )
        # With access_count=1, importance=5, just accessed: TTL = 168 * 1 * 1 * 1 = 168
        assert ttl == pytest.approx(168.0, rel=0.01)

    def test_high_access_extends_ttl(self):
        now = datetime.now(timezone.utc)
        ttl_low = compute_ttl_hours(
            last_accessed_at=now,
            access_count=1,
            importance_score=5.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        ttl_high = compute_ttl_hours(
            last_accessed_at=now,
            access_count=100,
            importance_score=5.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        assert ttl_high > ttl_low

    def test_high_importance_extends_ttl(self):
        now = datetime.now(timezone.utc)
        ttl_low = compute_ttl_hours(
            last_accessed_at=now,
            access_count=1,
            importance_score=2.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        ttl_high = compute_ttl_hours(
            last_accessed_at=now,
            access_count=1,
            importance_score=9.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        assert ttl_high > ttl_low

    def test_old_access_reduces_ttl(self):
        now = datetime.now(timezone.utc)
        ttl_recent = compute_ttl_hours(
            last_accessed_at=now,
            access_count=1,
            importance_score=5.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        ttl_old = compute_ttl_hours(
            last_accessed_at=now - timedelta(days=7),
            access_count=1,
            importance_score=5.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        assert ttl_old < ttl_recent

    def test_zero_importance(self):
        # Audit C5 / forgetting F1: importance 0 is a valid neutral value, not a
        # "delete me now" signal. It is treated as the neutral midpoint (5.0),
        # so the TTL must be positive (and equal to the importance-5 TTL), never
        # collapse to 0 (which previously caused immediate next-sweep deletion).
        now = datetime.now(timezone.utc)
        ttl = compute_ttl_hours(
            last_accessed_at=now,
            access_count=1,
            importance_score=0.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        ttl_neutral = compute_ttl_hours(
            last_accessed_at=now,
            access_count=1,
            importance_score=5.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        assert ttl > 0.0
        assert ttl == pytest.approx(ttl_neutral)

    def test_never_negative(self):
        now = datetime.now(timezone.utc)
        ttl = compute_ttl_hours(
            last_accessed_at=now - timedelta(days=365),
            access_count=1,
            importance_score=1.0,
            base_ttl_hours=168,
            decay_factor=0.693,
            now=now,
        )
        assert ttl >= 0.0
