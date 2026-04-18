"""Tests for retrieval scoring."""

import math
from datetime import datetime, timedelta, timezone

from hippocampus.retrieval.scorer import (
    compute_composite_score,
    compute_importance_score,
    compute_recency_score,
)
from hippocampus.embedding.utils import cosine_similarity


class TestScoring:
    def test_recency_score_recent(self):
        now = datetime.now(timezone.utc)
        score = compute_recency_score(now, now)
        assert score == pytest.approx(1.0)

    def test_recency_score_decay(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=24)
        score = compute_recency_score(old, now)
        assert 0 < score < 1.0

    def test_importance_normalization(self):
        assert compute_importance_score(0) == 0.0
        assert compute_importance_score(5) == 0.5
        assert compute_importance_score(10) == 1.0

    def test_composite_score(self):
        score = compute_composite_score(
            recency=0.8, importance=0.6, relevance=0.9,
            weight_recency=1.0, weight_importance=1.0, weight_relevance=1.0,
        )
        expected = (0.8 + 0.6 + 0.9) / 3
        assert score == pytest.approx(expected)

    def test_composite_score_weights(self):
        # Only relevance matters
        score = compute_composite_score(
            recency=0.1, importance=0.1, relevance=0.9,
            weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0,
        )
        assert score == pytest.approx(0.9)

    def test_composite_score_zero_weights(self):
        score = compute_composite_score(
            recency=0.5, importance=0.5, relevance=0.5,
            weight_recency=0.0, weight_importance=0.0, weight_relevance=0.0,
        )
        assert score == 0.0


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 0.0]
        assert cosine_similarity(a, b) == 0.0


import pytest
