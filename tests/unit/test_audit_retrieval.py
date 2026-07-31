"""Audit lane F (retrieval) regression tests.

Covers the C5 (recall calibration) and C6 (graph partition scoping) fixes in
``hebb.retrieval.searcher``:

* A genuinely relevant but low-sigmoid reranked hit survives the strict
  ``min_score`` floor, because the floor is now applied on the rerank scale for
  the reranked pool (not the composite scale).
* The graph channel honours ``partition_ids`` — cross-partition memories
  reachable from a matched tag are discarded.
* Recency uses the configured decay base (``_RECENCY_DECAY_FACTOR``), not the
  old silent ``0.99``.
* IDF is wired into the calibrated lexical relevance (``_build_idf`` is called
  with the query's surface tokens + partition scope).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import Memory, MemoryQuery
from hebb.retrieval.scorer import compute_recency_score
from hebb.retrieval.searcher import _RECENCY_DECAY_FACTOR, MemorySearcher

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeEmbedder:
    """Constant non-empty embedding so the vector path runs."""

    @property
    def dimension(self) -> int:
        """Fixed dimensionality matching the constant embedding below."""
        return 3

    async def embed(self, text: str) -> list[float]:
        """Return the constant 3-d vector so the vector path produces a hit."""
        return [0.1, 0.2, 0.3]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one constant vector per input — batch form of :meth:`embed`."""
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def aclose(self) -> None:  # pragma: no cover - no resources
        """No resources to release."""
        return None


class FakeStore:
    """Minimal MemoryStore stand-in for the searcher's read paths.

    Holds an in-memory ``{id: Memory}`` corpus and records the partition scope
    each method was called with, so tests can assert partition threading.
    """

    def __init__(self, memories: list[Memory]) -> None:
        self._by_id = {m.id: m for m in memories}
        self.corpus_size_calls: list[list[str] | None] = []
        self.doc_freq_calls: list[tuple[list[str], list[str] | None]] = []

    async def get(self, memory_id: str) -> Memory | None:
        """Return the memory for ``memory_id`` or ``None`` if absent."""
        return self._by_id.get(memory_id)

    async def search_by_vector(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        """Return no vector hits — vector recall is patched per-test."""
        return []

    async def search_by_keyword(
        self,
        query: str,
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        """Return no keyword hits — keyword recall is patched per-test."""
        return []

    async def corpus_size(self, partition_ids: list[str] | None = None) -> int:
        """Record the partition scope and report the in-memory corpus size."""
        self.corpus_size_calls.append(partition_ids)
        return len(self._by_id)

    async def keyword_doc_freqs(
        self, terms: list[str], partition_ids: list[str] | None = None
    ) -> dict[str, int]:
        """Record the terms + scope and return a flat DF of 1 per term."""
        self.doc_freq_calls.append((list(terms), partition_ids))
        return {t: 1 for t in terms}

    async def update_access_batch(self, memory_ids: list[str]) -> None:  # pragma: no cover
        """No-op access-time update — the audit path doesn't assert on it."""
        return None


class FakeReranker:
    """Returns a fixed sigmoid-scale score for every candidate."""

    def __init__(self, score: float, top_n: int = 30) -> None:
        self._score = score
        self._top_n = top_n

    @property
    def top_n(self) -> int:
        """Rerank pool size the searcher slices candidates to."""
        return self._top_n

    async def score(self, query: str, candidates: list[str]) -> list[float]:
        """Return the fixed score for every candidate, preserving input order."""
        return [self._score for _ in candidates]


def _mem(content: str, *, partition_id: str = "mem_hippocampus", mid: str | None = None) -> Memory:
    if mid is not None:
        return Memory(id=mid, content=content, partition_id=partition_id)
    return Memory(content=content, partition_id=partition_id)


def _searcher_with_vector_hit(
    mem: Memory,
    *,
    reranker: FakeReranker | None,
    store: FakeStore | None = None,
) -> MemorySearcher:
    """Searcher whose vector channel returns ``mem`` at a strong cosine.

    The cosine becomes the no-rerank composite relevance; when a reranker is
    attached its sigmoid score replaces it, so we can isolate the floor scale.
    """
    store = store or FakeStore([mem])

    async def _vec(self: MemorySearcher, query: str, top_k: int, partition_ids: list[str] | None):
        return [(mem, 0.95)]

    searcher = MemorySearcher(
        store=store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        graph=None,
        reranker=reranker,
        graph_search_enabled=False,
        graph_expansion_enabled=False,
    )
    # Patch the vector path on this instance so the candidate enters the pool.
    searcher._vector_search = _vec.__get__(searcher, MemorySearcher)  # type: ignore[method-assign]
    return searcher


# ---------------------------------------------------------------------------
# C5: strict-recall floor applied on the correct (rerank) scale
# ---------------------------------------------------------------------------


async def test_low_sigmoid_hit_survives_strict_floor() -> None:
    """A relevant hit scoring a 0.6 bge sigmoid must NOT be dropped by a 0.8
    *composite* strict floor — the floor is translated to the rerank scale for
    reranked entries."""
    mem = _mem("the capital of sweden is stockholm")
    searcher = _searcher_with_vector_hit(mem, reranker=FakeReranker(0.6))

    query = MemoryQuery(query="what is the capital of sweden", min_score=0.8)
    resp = await searcher.search(query)

    assert [r.memory.id for r in resp.results] == [mem.id]
    # The result carries the rerank sigmoid, unchanged by the floor.
    assert resp.results[0].score == 0.6


async def test_below_rerank_floor_hit_is_dropped() -> None:
    """A weak reranked hit (sigmoid below the translated rerank floor) is still
    dropped — the floor is relaxed, not removed."""
    mem = _mem("a totally unrelated note about gardening")
    searcher = _searcher_with_vector_hit(mem, reranker=FakeReranker(0.2))

    query = MemoryQuery(query="what is the capital of sweden", min_score=0.8)
    resp = await searcher.search(query)

    assert resp.results == []


async def test_no_rerank_floor_uses_composite_scale() -> None:
    """Without a reranker the floor reads the composite ``score`` directly; a
    strong calibrated hit clears it."""
    mem = _mem("what is the capital of sweden stockholm")
    searcher = _searcher_with_vector_hit(mem, reranker=None)

    query = MemoryQuery(query="what is the capital of sweden", min_score=0.5)
    resp = await searcher.search(query)

    assert [r.memory.id for r in resp.results] == [mem.id]


async def test_custom_rerank_floor_ratio_tight() -> None:
    """A higher ratio tightens the rerank-scale floor, dropping a marginal
    sigmoid hit that the default 0.625 ratio would have let through."""
    mem = _mem("the capital of sweden is stockholm")
    searcher = _searcher_with_vector_hit(mem, reranker=FakeReranker(0.6))

    query = MemoryQuery(query="what is the capital of sweden", min_score=0.8)

    # Default ratio 0.625: rerank_floor = 0.8 * 0.625 = 0.5 → 0.6 survives.
    resp = await searcher.search(query)
    assert [r.memory.id for r in resp.results] == [mem.id]

    # Custom ratio 0.9: rerank_floor = 0.8 * 0.9 = 0.72 → 0.6 is dropped.
    resp = await searcher.search(query, rerank_floor_ratio=0.9)
    assert resp.results == []


async def test_custom_rerank_floor_ratio_lenient() -> None:
    """A lower ratio relaxes the rerank-scale floor, letting a weak sigmoid
    hit through that the default 0.625 ratio would have dropped."""
    mem = _mem("a somewhat relevant note about nordic countries")
    searcher = _searcher_with_vector_hit(mem, reranker=FakeReranker(0.35))

    query = MemoryQuery(query="what is the capital of sweden", min_score=0.8)

    # Default ratio 0.625: rerank_floor = 0.8 * 0.625 = 0.5 → 0.35 is dropped.
    resp = await searcher.search(query)
    assert resp.results == []

    # Custom ratio 0.3: rerank_floor = 0.8 * 0.3 = 0.24 → 0.35 survives.
    resp = await searcher.search(query, rerank_floor_ratio=0.3)
    assert [r.memory.id for r in resp.results] == [mem.id]


# ---------------------------------------------------------------------------
# C6: graph channel respects partition_ids
# ---------------------------------------------------------------------------


async def test_graph_search_filters_by_partition(tmp_path: Path) -> None:
    """A memory reachable from a matched tag but in a different partition is
    discarded when the query scopes partitions."""
    in_part = _mem("sweden travel notes", partition_id="p1", mid="m-in")
    out_part = _mem("sweden travel notes", partition_id="p2", mid="m-out")
    store = FakeStore([in_part, out_part])

    graph = KnowledgeGraph(tmp_path / "graph.json")
    graph.add_tag("sweden", "m-in")
    graph.add_tag("sweden", "m-out")

    searcher = MemorySearcher(
        store=store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        graph=graph,
    )

    scoped = await searcher._graph_search("sweden", 10, ["p1"])
    assert {m.id for m, _ in scoped} == {"m-in"}

    unscoped = await searcher._graph_search("sweden", 10, None)
    assert {m.id for m, _ in unscoped} == {"m-in", "m-out"}


# ---------------------------------------------------------------------------
# forgetting F2: recency uses the configured decay base, not 0.99
# ---------------------------------------------------------------------------


def test_recency_uses_configured_decay() -> None:
    """The module decay constant matches the configured ``Settings`` default and
    differs from the old silent 0.99 — so recency actually decays."""
    assert _RECENCY_DECAY_FACTOR == 0.693

    now = datetime.now(timezone.utc)
    last = now - timedelta(hours=24)
    configured = compute_recency_score(last, now, _RECENCY_DECAY_FACTOR)
    silent = compute_recency_score(last, now, 0.99)

    # 0.693**24 is far below 0.99**24 — the fix makes recency meaningful.
    assert configured < 0.01 < silent


# ---------------------------------------------------------------------------
# recall F2: IDF is wired through with the right surface tokens + scope
# ---------------------------------------------------------------------------


async def test_idf_wired_with_surface_tokens_and_partition_scope() -> None:
    """``_build_idf`` fetches corpus size + doc freqs for the query's surface
    tokens, scoped to the query's partitions."""
    store = FakeStore([_mem("stockholm is the capital of sweden", partition_id="p1")])
    searcher = MemorySearcher(
        store=store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        graph=None,
        graph_search_enabled=False,
        graph_expansion_enabled=False,
    )

    idf = await searcher._build_idf("capital of sweden", ["p1"])
    assert idf is not None

    assert store.corpus_size_calls == [["p1"]]
    assert len(store.doc_freq_calls) == 1
    terms, scope = store.doc_freq_calls[0]
    assert scope == ["p1"]
    # Stopword "of" is dropped; discriminating content terms are looked up.
    assert "capital" in terms
    assert "sweden" in terms
    assert "of" not in terms


async def test_build_idf_none_when_corpus_empty() -> None:
    """Empty corpus → no IDF (caller falls back to plain coverage)."""
    store = FakeStore([])
    searcher = MemorySearcher(
        store=store,  # type: ignore[arg-type]
        embedder=FakeEmbedder(),
        graph=None,
    )
    assert await searcher._build_idf("anything here", None) is None
