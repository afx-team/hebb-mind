"""QA accuracy and text similarity metrics."""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eval.benchmarks.base import RetrievalResult


def compute_accuracy(results: list[RetrievalResult]) -> float:
    """Overall accuracy: fraction of correct answers."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.is_correct) / len(results)


def compute_accuracy_by_category(
    results: list[RetrievalResult],
) -> dict[str, dict[str, float | int]]:
    """Accuracy broken down by question category.

    Returns {category: {correct, total, accuracy}}.
    """
    buckets: dict[str, list[bool]] = {}
    for r in results:
        buckets.setdefault(r.category, []).append(r.is_correct)
    return {
        cat: {
            "correct": sum(vals),
            "total": len(vals),
            "accuracy": sum(vals) / len(vals) if vals else 0.0,
        }
        for cat, vals in sorted(buckets.items())
    }


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def compute_f1(predicted: str, ground_truth: str) -> float:
    """Token-level F1 score between predicted and ground truth strings."""
    pred_tokens = Counter(_tokenize(predicted))
    gold_tokens = Counter(_tokenize(ground_truth))
    common = sum((pred_tokens & gold_tokens).values())
    if common == 0:
        return 0.0
    precision = common / sum(pred_tokens.values())
    recall = common / sum(gold_tokens.values())
    return 2 * precision * recall / (precision + recall)


def compute_exact_match(predicted: str, ground_truth: str) -> bool:
    """Normalized exact match comparison."""
    return _tokenize(predicted) == _tokenize(ground_truth)
