"""Retrieval quality metrics: Recall@k, Precision@k, MRR."""

from __future__ import annotations


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Fraction of relevant items found in the top-k retrieved results."""
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    hits = sum(1 for r in relevant if r in top_k)
    return hits / len(relevant)


def precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Fraction of top-k retrieved results that are relevant."""
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant)
    hits = sum(1 for r in top_k if r in relevant_set)
    return hits / len(top_k)


def mrr(retrieved: list[str], relevant: list[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of the first relevant result."""
    relevant_set = set(relevant)
    for i, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    import math

    relevant_set = set(relevant)
    dcg = 0.0
    for i, item in enumerate(retrieved[:k]):
        if item in relevant_set:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because i is 0-indexed

    # Ideal DCG: all relevant items ranked at top
    ideal_count = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))
    return dcg / idcg if idcg > 0 else 0.0
