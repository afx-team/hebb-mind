"""Memory search orchestrator — hybrid vector + keyword + graph retrieval."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from hippocampus.embedding.base import EmbeddingProvider
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.models.memory import Memory, MemoryQuery, MemorySearchResult, SearchResponse
from hippocampus.retrieval.scorer import (
    compute_composite_score,
    compute_importance_score,
    compute_recency_score,
)
from hippocampus.storage.base import MemoryStore


class MemorySearcher:
    """Orchestrates hybrid retrieval: vector + keyword + graph, then scoring.

    Three-path parallel recall:
        1. Vector path  — embedding cosine/L2 similarity
        2. Keyword path — FTS5 (SQLite) / tsvector (PostgreSQL)
        3. Graph path   — query → match tags → expand neighbors → collect memory_ids

    Post-expansion:
        After scoring, extract tags from top results, expand via graph,
        and return additional related memories.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedder: EmbeddingProvider,
        graph: KnowledgeGraph | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.graph = graph

    async def search(self, query: MemoryQuery) -> SearchResponse:
        now = datetime.now(timezone.utc)
        overfetch = query.top_k * 3

        # === Phase 1: Three-path parallel recall ===
        vec_results, kw_results, graph_results = await asyncio.gather(
            self._vector_search(query.query, overfetch, query.partition_ids),
            self._keyword_search(query.query, overfetch, query.partition_ids),
            self._graph_search(query.query, overfetch),
        )

        # Merge by memory ID, take max relevance score
        merged: dict[str, tuple[Memory, float]] = {}
        for mem, score in [*vec_results, *kw_results, *graph_results]:
            if mem.id in merged:
                existing = merged[mem.id]
                merged[mem.id] = (existing[0], max(existing[1], score))
            else:
                merged[mem.id] = (mem, score)

        # Tag filter + composite scoring
        results: list[MemorySearchResult] = []
        for memory, relevance in merged.values():
            if query.tags and not set(query.tags).intersection(memory.tags):
                continue

            recency = compute_recency_score(memory.last_accessed_at, now)
            importance_norm = compute_importance_score(memory.importance_score)

            score = compute_composite_score(
                recency=recency,
                importance=importance_norm,
                relevance=relevance,
                weight_recency=query.weight_recency,
                weight_importance=query.weight_importance,
                weight_relevance=query.weight_relevance,
            )

            results.append(
                MemorySearchResult(
                    memory=memory,
                    score=score,
                    recency_score=recency,
                    importance_score_normalized=importance_norm,
                    relevance_score=relevance,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        top_results = results[: query.top_k]

        # === Phase 2: Post-expansion via graph ===
        related = await self._graph_expand_from_results(
            top_results, exclude_ids={r.memory.id for r in top_results}, limit=5
        )

        return SearchResponse(results=top_results, related=related)

    # ------------------------------------------------------------------
    # Path 1: Vector retrieval
    # ------------------------------------------------------------------

    async def _vector_search(
        self, query: str, top_k: int, partition_ids: list[str] | None
    ) -> list[tuple[Memory, float]]:
        embedding = await self.embedder.embed(query)
        if not embedding:
            return []
        return await self.store.search_by_vector(
            query_embedding=embedding,
            top_k=top_k,
            partition_ids=partition_ids,
        )

    # ------------------------------------------------------------------
    # Path 2: Keyword retrieval (FTS5 / tsvector)
    # ------------------------------------------------------------------

    async def _keyword_search(
        self, query: str, top_k: int, partition_ids: list[str] | None
    ) -> list[tuple[Memory, float]]:
        return await self.store.search_by_keyword(
            query=query,
            top_k=top_k,
            partition_ids=partition_ids,
        )

    # ------------------------------------------------------------------
    # Path 3: Graph retrieval (query → match tags → expand → memories)
    # ------------------------------------------------------------------

    async def _graph_search(self, query: str, top_k: int) -> list[tuple[Memory, float]]:
        """Match query words against graph tags, expand 1 hop, collect memories."""
        if not self.graph:
            return []

        # Find tags matching query keywords
        matched_tags = self.graph.search_tags(query)
        if not matched_tags:
            return []

        # Collect memory_ids from matched tags + their 1-hop neighbors
        memory_ids: set[str] = set()
        for tag in matched_tags:
            memory_ids.update(tag.memory_ids)
            # Expand 1 hop
            neighbors = self.graph.query_neighbors(tag.id, depth=1)
            for neighbor_node in neighbors.nodes:
                memory_ids.update(neighbor_node.memory_ids)

        # Fetch actual memories and assign relevance based on tag match strength
        results: list[tuple[Memory, float]] = []
        for mid in list(memory_ids)[:top_k]:
            memory = await self.store.get(mid)
            if memory:
                # Score: matched tags with high weight get higher relevance
                max_weight = max((t.weight for t in matched_tags), default=1.0)
                similarity = min(0.5 + 0.5 * (max_weight / max(max_weight, 5.0)), 0.9)
                results.append((memory, similarity))

        return results

    # ------------------------------------------------------------------
    # Post-expansion: top results → extract tags → graph expand → related
    # ------------------------------------------------------------------

    async def _graph_expand_from_results(
        self,
        results: list[MemorySearchResult],
        exclude_ids: set[str],
        limit: int = 5,
    ) -> list[Memory]:
        """Expand from tags of top results to find related memories."""
        if not self.graph or not results:
            return []

        # Collect all tags from top results
        result_tags: set[str] = set()
        for r in results:
            result_tags.update(t.lower().strip() for t in r.memory.tags)

        # Expand each tag 1 hop and collect neighbor memory_ids
        related_ids: set[str] = set()
        for tag in result_tags:
            neighbors = self.graph.query_neighbors(tag, depth=1)
            for node in neighbors.nodes:
                related_ids.update(node.memory_ids)

        # Remove already-returned memory IDs
        related_ids -= exclude_ids

        # Fetch and return
        related: list[Memory] = []
        for mid in list(related_ids)[:limit]:
            memory = await self.store.get(mid)
            if memory:
                related.append(memory)

        return related
