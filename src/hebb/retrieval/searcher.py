"""Memory search orchestrator — hybrid vector + keyword + graph retrieval."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import Memory, MemoryQuery, MemorySearchResult, SearchResponse
from hebb.retrieval.keyword_rank import blend_keyword_rank
from hebb.retrieval.lexical_relevance import build_lexical_query, lexical_relevance
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
        vector_search_enabled: bool = True,
        keyword_search_enabled: bool = True,
        graph_search_enabled: bool = True,
        lexical_boost_enabled: bool = True,
        temporal_boost_enabled: bool = True,
        graph_expansion_enabled: bool = True,
        keyword_blend_enabled: bool = True,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.graph = graph
        self.reranker = reranker
        # Pipeline toggles — each defaults True so callers that don't
        # opt-in to ablation get the current behaviour bit-for-bit.
        self.vector_search_enabled = vector_search_enabled
        self.keyword_search_enabled = keyword_search_enabled
        self.graph_search_enabled = graph_search_enabled
        self.lexical_boost_enabled = lexical_boost_enabled
        self.temporal_boost_enabled = temporal_boost_enabled
        self.graph_expansion_enabled = graph_expansion_enabled
        # Blend re-rank the keyword channel (BM25 × coverage/proximity) — lifts
        # its intrinsic top-1/top-k so it stands on its own (and feeds RRF a
        # better rank) without depending on the cross-encoder reranker.
        self.keyword_blend_enabled = keyword_blend_enabled

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

        vec_task = (
            self._vector_search(query.query, overfetch, query.partition_ids)
            if self.vector_search_enabled
            else _empty_ranked()
        )
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

        # Semantic similarity per candidate, keyed by id. The vector channel
        # now returns *true* cosine in [0, 1] (unrelated docs ≈ 0), so it can
        # serve directly as a calibrated semantic relevance.
        sem_sims: dict[str, float] = {mem.id: sim for mem, sim in vec_results}

        # Absolute keyword relevance comparator: IDF-less coverage + proximity
        # in [0, 1], computed per (query, content) — on the same scale as the
        # vector cosine, so the two channels are directly comparable (the
        # "类比关系") and the min_score floor means the same thing for both.
        # Parsed once; ``lexical_relevance`` is applied per candidate below.
        lexical_query = build_lexical_query(query.query)

        # Surface-overlap signals for the *ranking* nudge (unchanged from the
        # tuned hybrid stack): a small multiplicative lift on the RRF relevance
        # so lexically-matching candidates rank a touch higher. This affects
        # ORDER only — the calibrated relevance below is what callers see and
        # what the min_score floor reads.
        query_signals = extract_query_signals(query.query)

        # Tag filter + scoring. We keep two scores per candidate:
        #   * rank_score — the RRF-fusion composite (recall-tuned, carries the
        #     keyword channel's blend-improved rank), used to ORDER results and
        #     feed rerank.
        #   * display score / relevance_score — ``max(keyword_blend, cosine)``,
        #     each channel on a [0, 1] scale, so the keyword score is directly
        #     comparable to the vector score (the "类比关系" the caller and the
        #     min_score floor need). This is the VALUE, not the order.
        scored: list[tuple[float, MemorySearchResult]] = []
        for memory, rrf_relevance in merged.values():
            if query.tags and not set(query.tags).intersection(memory.tags):
                continue

            recency = compute_recency_score(memory.last_accessed_at, now)
            importance_norm = compute_importance_score(memory.importance_score)

            # Per-channel [0, 1] relevance VALUE: absolute keyword coverage and
            # semantic cosine. MAX — a doc strongly matched by EITHER channel
            # reads as relevant, both on the same scale (comparable without a
            # reranker, and the 0.8 floor means the same for each).
            lex_rel = lexical_relevance(lexical_query, memory.content)
            sem_rel = sem_sims.get(memory.id, 0.0)
            calibrated = max(lex_rel, sem_rel)

            # ORDERING stays on the recall-tuned RRF rank (with the surface-
            # overlap nudge): the keyword channel feeds RRF its blend-improved
            # rank, so RRF already carries the keyword top-1 gain, and RRF's
            # rank order is more robust than ordering by the calibrated value
            # (which, ordered directly, regressed LoCoMo via the turn-window
            # interaction). Scoring is the calibrated value; ordering is RRF.
            rank_relevance = rrf_relevance
            if self.lexical_boost_enabled and not query_signals.is_empty:
                rank_relevance = min(1.0, rank_relevance * lexical_boost(query_signals, memory.content))

            rank_score = compute_composite_score(
                recency=recency,
                importance=importance_norm,
                relevance=rank_relevance,
                weight_recency=query.weight_recency,
                weight_importance=query.weight_importance,
                weight_relevance=query.weight_relevance,
            )
            disp_score = compute_composite_score(
                recency=recency,
                importance=importance_norm,
                relevance=calibrated,
                weight_recency=query.weight_recency,
                weight_importance=query.weight_importance,
                weight_relevance=query.weight_relevance,
            )

            # Date proximity boost: when the query names "August 2023" or
            # "last week", up-weight candidates whose metadata.timestamp
            # falls in that window. Applied to both scores so date matches
            # rank higher *and* read as more relevant; capped at 1.0.
            if self.temporal_boost_enabled and query_dates:
                ts = memory.metadata.model_dump().get("timestamp")
                boost = temporal_boost(str(ts) if ts else None, query_dates)
                if boost > 0:
                    rank_score = min(1.0, rank_score * (1.0 + boost))
                    disp_score = min(1.0, disp_score * (1.0 + boost))

            scored.append(
                (
                    rank_score,
                    MemorySearchResult(
                        memory=memory,
                        score=disp_score,
                        recency_score=recency,
                        importance_score_normalized=importance_norm,
                        relevance_score=calibrated,
                    ),
                )
            )

        # Order by the recall-tuned RRF rank (carries the keyword channel's
        # blend-improved rank); the calibrated max-channel score is the value.
        scored.sort(key=lambda rs: rs[0], reverse=True)
        results: list[MemorySearchResult] = [r for _, r in scored]

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

        # Relevance floor: drop anything below min_score. The composite is
        # bounded to [0, 1] by construction (each signal is in [0, 1] and the
        # weights are normalised) and rerank scores are sigmoid-normalised, so
        # the floor lives on a [0, 1] scale in both modes. Used by strict recall
        # surfaces (hook, MCP); 0.0 (console default) is a no-op.
        if query.min_score > 0.0:
            results = [r for r in results if r.score >= query.min_score]

        # Final ordering. When the cross-encoder reranker ran, ``score`` is its
        # joint (query, content) relevance — a strong ranker — so order by it.
        # WITHOUT rerank, ``score`` is the calibrated lexical/semantic relevance,
        # which is a good *value* (for the min_score floor) but a worse *ranker*
        # than the recall-tuned RRF+blend rank: re-sorting by it measurably
        # hurts top-1 (it overrides the keyword channel's blend-improved rank).
        # So keep the RRF rank order when not reranking — basic retrieval
        # quality first, monotonic-display-vs-score second.
        top_results = results[: query.top_k]
        if self.reranker is not None:
            top_results.sort(key=lambda r: r.score, reverse=True)
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
        candidates = await self.store.search_by_keyword(
            query=query,
            top_k=top_k,
            partition_ids=partition_ids,
        )
        # Blend re-rank: BM25 magnitude × query-term coverage/proximity. Lifts
        # the keyword channel's intrinsic top-1/top-k (the channel is
        # ranking-limited — the right doc is in-pool but BM25 ranks it low).
        # Cheap (no DB round-trips). The improved order feeds RRF.
        if self.keyword_blend_enabled and len(candidates) > 1:
            candidates = blend_keyword_rank(query, candidates)
        return candidates

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
