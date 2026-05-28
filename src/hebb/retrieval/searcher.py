"""Memory search orchestrator — hybrid vector + keyword + graph retrieval."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import Memory, MemoryQuery, MemorySearchResult, SearchResponse
from hebb.retrieval.lexical_signals import extract_query_signals, lexical_boost
from hebb.retrieval.query_sanitizer import sanitize_query
from hebb.retrieval.rerank import Reranker
from hebb.retrieval.scorer import (
    compute_composite_score,
    compute_importance_score,
    compute_recency_score,
)
from hebb.retrieval.temporal_boost import parse_query_dates, temporal_boost
from hebb.storage.base import MemoryStore


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
        reranker: Reranker | None = None,
        *,
        keyword_search_enabled: bool = True,
        graph_search_enabled: bool = True,
        lexical_boost_enabled: bool = True,
        temporal_boost_enabled: bool = True,
        graph_expansion_enabled: bool = True,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.graph = graph
        self.reranker = reranker
        # Pipeline toggles — each defaults True so callers that don't
        # opt-in to ablation get the current behaviour bit-for-bit.
        self.keyword_search_enabled = keyword_search_enabled
        self.graph_search_enabled = graph_search_enabled
        self.lexical_boost_enabled = lexical_boost_enabled
        self.temporal_boost_enabled = temporal_boost_enabled
        self.graph_expansion_enabled = graph_expansion_enabled

    async def search(self, query: MemoryQuery) -> SearchResponse:
        # Sanitize LLM-generated queries (XML tags, tool artifacts, etc.)
        sanitized = sanitize_query(query.query)
        if sanitized != query.query:
            query = query.model_copy(update={"query": sanitized})

        now = datetime.now(timezone.utc)
        # Overfetch generously so RRF has long ranked lists to merge across.
        # When rerank is enabled, ensure the candidate pool is at least as
        # deep as what rerank scores — otherwise rerank can't recover an
        # answer that never made it past the recall phase.
        rerank_top_n = self.reranker.top_n if self.reranker is not None else 0
        overfetch = max(query.top_k * 6, rerank_top_n, 30)

        # === Phase 1: Three-path parallel recall ===
        # Each path is independently toggleable. Disabled paths return
        # an empty ranked list so RRF merges over only the enabled
        # channels. All three paths return list[tuple[Memory, float]].
        async def _empty_ranked() -> list[tuple[Memory, float]]:
            return []

        vec_task = self._vector_search(query.query, overfetch, query.partition_ids)
        kw_task = (
            self._keyword_search(query.query, overfetch, query.partition_ids)
            if self.keyword_search_enabled
            else _empty_ranked()
        )
        graph_task = self._graph_search(query.query, overfetch) if self.graph_search_enabled else _empty_ranked()
        vec_results, kw_results, graph_results = await asyncio.gather(vec_task, kw_task, graph_task)

        # Reciprocal Rank Fusion across the three retrieval channels.
        # Each channel contributes 1/(k+rank) to a memory's relevance, so a
        # document hit by multiple channels accumulates a higher score than
        # one that only tops a single channel — strictly better than the
        # previous max() merge when keyword and vector signals disagree.
        merged = self._fuse_rrf(vec_results, kw_results, graph_results)

        # Parse query once for date anchors used by the temporal boost
        # below. Reference for relative phrases is "today" — for
        # historical replay we trust the absolute anchors only.
        query_dates = parse_query_dates(query.query, reference=now.date())

        # Extract lexical re-ranking signals once per search — predicate
        # keywords, quoted phrases, person names. Used to multiplicatively
        # lift candidates that share these surface tokens with the query.
        # Cheap (regex only) but skipped when the query has no extractable
        # signals to keep the fast path tight.
        query_signals = extract_query_signals(query.query)

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

            # Date proximity boost: when the query names "August 2023" or
            # "last week", up-weight candidates whose metadata.timestamp
            # falls in that window. Decays linearly past tolerance, capped
            # at 1.0 so the boosted score still fits the composite scale.
            if self.temporal_boost_enabled and query_dates:
                ts = memory.metadata.model_dump().get("timestamp")
                boost = temporal_boost(str(ts) if ts else None, query_dates)
                if boost > 0:
                    score = min(1.0, score * (1.0 + boost))

            # Lexical surface boost: predicate-keyword / quoted-phrase /
            # person-name overlap. Multiplier sits in [1.0, ~2.3]. We
            # do NOT cap at 1.0 here — capping would collapse the
            # differentiation between two near-top candidates and lose
            # the ranking signal the boost is trying to inject. The
            # final sort cares about relative ordering, not absolute
            # range.
            if self.lexical_boost_enabled and not query_signals.is_empty:
                score = score * lexical_boost(query_signals, memory.content)

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

        # === Phase 1.6: cross-encoder rerank (optional) ===
        # Re-score the top-N composite candidates with a cross-encoder
        # that reads (query, content) jointly. Cross-attention catches
        # semantic matches that vector + lexical can't (e.g. "upgrade
        # camera flash" ↔ "suggest accessories"). Skipped entirely when
        # self.reranker is None — that branch is indistinguishable from
        # the pre-rerank code path.
        if self.reranker is not None and results:
            pool = results[: self.reranker.top_n]
            tail = results[self.reranker.top_n :]
            rerank_scores = await self.reranker.score(query.query, [r.memory.content for r in pool])
            for r, s in zip(pool, rerank_scores, strict=False):
                r.score = float(s)
                r.relevance_score = float(s)
            pool.sort(key=lambda r: r.score, reverse=True)
            results = pool + tail

        top_results = results[: query.top_k]
        top_ids = {r.memory.id for r in top_results}

        # === Phase 2a: Turn-window expansion ===
        # Pull adjacent turns from the same session for each hit. The
        # context window is the cheapest way to recover multi-hop facts
        # that span 2–3 consecutive utterances ("home country" + "Sweden",
        # "I read a book" + "by Tom Oliver").
        turn_neighbours: list[Memory] = []
        if query.prev_turns > 0 or query.next_turns > 0:
            turn_neighbours = await self._expand_turn_window(
                top_results,
                prev_turns=query.prev_turns,
                next_turns=query.next_turns,
                exclude_ids=top_ids,
            )

        # === Phase 2b: Post-expansion via graph ===
        if self.graph_expansion_enabled:
            exclude_for_graph = top_ids | {m.id for m in turn_neighbours}
            graph_related = await self._graph_expand_from_results(top_results, exclude_ids=exclude_for_graph, limit=5)
        else:
            graph_related = []

        related: list[Memory] = [*turn_neighbours, *graph_related]
        return SearchResponse(results=top_results, related=related)

    # ------------------------------------------------------------------
    # Turn-window expansion
    # ------------------------------------------------------------------

    async def _expand_turn_window(
        self,
        results: list[MemorySearchResult],
        *,
        prev_turns: int,
        next_turns: int,
        exclude_ids: set[str],
    ) -> list[Memory]:
        """For each hit with session_id+turn metadata, fetch the
        surrounding ±N turns from the same session/partition.

        Deduplicates across hits so a memory adjacent to two different
        top-k results only surfaces once.
        """
        if not results:
            return []

        seen_ids: set[str] = set(exclude_ids)
        out: list[Memory] = []

        for r in results:
            md = r.memory.metadata.model_dump()
            session_id = md.get("session_id")
            if not session_id:
                continue

            # The hit's turn anchor: either `turn` (per-utterance) or
            # the span of `turn_pair` (per-turn-pair summary).
            anchors: list[int] = []
            if isinstance(md.get("turn"), int):
                anchors.append(int(md["turn"]))
            pair = md.get("turn_pair") or []
            if isinstance(pair, list):
                anchors.extend(int(t) for t in pair if isinstance(t, int))
            if not anchors:
                continue

            anchor_min, anchor_max = min(anchors), max(anchors)
            window_min = anchor_min - prev_turns
            window_max = anchor_max + next_turns

            neighbours = await self.store.get_turn_neighbors(
                partition_id=r.memory.partition_id,
                session_id=str(session_id),
                turn_min=window_min,
                turn_max=window_max,
                exclude_ids=list(seen_ids),
            )
            for n in neighbours:
                if n.id in seen_ids:
                    continue
                seen_ids.add(n.id)
                out.append(n)

        return out

    # ------------------------------------------------------------------
    # Fusion
    # ------------------------------------------------------------------

    @staticmethod
    def _fuse_rrf(
        *ranked_lists: list[tuple[Memory, float]],
        k: int = 60,
    ) -> dict[str, tuple[Memory, float]]:
        """Reciprocal Rank Fusion of multiple ranked retrieval lists.

        Args:
            ranked_lists: One list per retrieval channel, each already
                sorted by that channel's own score (highest first).
            k: Standard RRF dampening constant. Larger ``k`` flattens the
                contribution gap between top ranks; 60 is the value from the
                original RRF paper and balances precision with diversity.

        Returns:
            ``{memory_id: (Memory, fused_score)}`` where ``fused_score`` is
            the sum of ``1 / (k + rank_in_channel)`` contributions, capped
            at ``1.0`` so downstream composite scoring stays in ``[0, 1]``.
        """
        merged: dict[str, tuple[Memory, float]] = {}
        for ranked in ranked_lists:
            for rank, (memory, _channel_score) in enumerate(ranked):
                contribution = 1.0 / (k + rank + 1)
                if memory.id in merged:
                    existing_mem, existing_score = merged[memory.id]
                    merged[memory.id] = (existing_mem, existing_score + contribution)
                else:
                    merged[memory.id] = (memory, contribution)

        # Normalise into [0, 1] so the composite scorer (which mixes
        # relevance with recency/importance — all already in [0, 1]) keeps
        # comparable units. Max possible per memory is bounded by the number
        # of channels: 3 * 1/(k+1).
        max_per_hit = 3.0 / (k + 1)
        return {mid: (mem, min(score / max_per_hit, 1.0)) for mid, (mem, score) in merged.items()}

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
