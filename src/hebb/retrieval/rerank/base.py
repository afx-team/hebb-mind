"""Abstract reranker protocol."""

from __future__ import annotations

from typing import Protocol


class Reranker(Protocol):
    """Cross-encoder style reranker.

    Rescore the top-N candidates from hybrid retrieval by feeding
    ``(query, candidate_content)`` pairs through a model trained for
    relevance scoring. Returned scores are arbitrary-scale; only their
    relative ordering matters.
    """

    @property
    def top_n(self) -> int:
        """Max candidates to rerank per query."""
        ...

    async def score(self, query: str, candidates: list[str]) -> list[float]:
        """Return one score per candidate; higher = more relevant."""
        ...
