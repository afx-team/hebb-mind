"""IDF statistic cache regression tests (issue #54).

``MemorySearcher._build_idf`` reuses ``corpus_size`` and per-query document
frequencies across ``search()`` calls via two short-TTL, instance-level dicts,
so a repeated or overlapping query over an unchanged corpus skips the store
round-trip. These tests pin the four behaviours the issue calls out:

* Cache Hit     — identical re-search adds zero ``corpus_size`` / DF store calls.
* Cache Miss    — a fresh token set re-hits the store.
* TTL Expiry    — after the TTL elapses, a hit becomes a miss and re-fetches.
* Partition Isolation — different partition scopes get independent entries, and
  a DF entry keyed by one token does not leak into another token's score.

The store is a lightweight in-memory double that records every call, so the
assertions are about *call counts*, not clock-time latency.
"""

from __future__ import annotations

import asyncio

import pytest

from hebb.models.memory import Memory
from hebb.retrieval.searcher import MemorySearcher

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Constant non-empty embedding so a ``MemorySearcher`` can be constructed."""

    @property
    def dimension(self) -> int:
        return 3

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def aclose(self) -> None:  # pragma: no cover - no resources
        return None


class _RecordingStore:
    """In-memory ``MemoryStore`` stand-in that counts every IDF-related call.

    Unlike the audit lane's ``FakeStore``, this one returns *distinct* document
    frequencies per term (``alpha`` is rare, ``beta`` is common) so partition
    isolation and cross-token leakage can be observed through the scores, not
    only the call counts.
    """

    def __init__(self, corpus_size: int, df_map: dict[str, int] | None = None) -> None:
        self._corpus_size = corpus_size
        self._df_map = df_map or {}
        self.corpus_size_calls: int = 0
        self.doc_freq_calls: int = 0

    # --- read paths the searcher touches via _build_idf -------------------

    async def corpus_size(self, partition_ids: list[str] | None = None) -> int:
        self.corpus_size_calls += 1
        return self._corpus_size

    async def keyword_doc_freqs(self, terms: list[str], partition_ids: list[str] | None = None) -> dict[str, int]:
        self.doc_freq_calls += 1
        # Default absent terms to df 1 (the store's "best-effort" convention):
        # an unseen query term is treated as rare, not zero.
        return {term: self._df_map.get(term, 1) for term in terms}

    # --- out-of-path MemoryStore methods the searcher may touch on search -

    async def get(self, memory_id: str) -> Memory | None:  # pragma: no cover
        return None

    async def search_by_vector(  # pragma: no cover
        self,
        query_embedding: list[float],
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        return []

    async def search_by_keyword(  # pragma: no cover
        self,
        query: str,
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        return []

    async def update_access_batch(self, memory_ids: list[str]) -> None:  # pragma: no cover
        return None


def _make_searcher(store: _RecordingStore) -> MemorySearcher:
    """A searcher with every channel off — only ``_build_idf`` is exercised."""
    return MemorySearcher(
        store=store,  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),
        graph=None,
        graph_search_enabled=False,
        graph_expansion_enabled=False,
    )


def _df_map() -> dict[str, int]:
    # Rare "alpha" (df 1) vs common "beta" (df 5) make IDF *and* leakage observable.
    return {"alpha": 1, "beta": 5}


# ---------------------------------------------------------------------------
# Cache Hit / Miss
# ---------------------------------------------------------------------------


async def test_cache_hit_repeated_query_adds_no_store_calls() -> None:
    """An identical re-search reuses cached stats — zero extra store calls."""
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)

    await searcher._build_idf("alpha beta", ["p1"])
    first_corpus, first_df = store.corpus_size_calls, store.doc_freq_calls

    await searcher._build_idf("alpha beta", ["p1"])

    assert store.corpus_size_calls == first_corpus  # no new corpus_size hit
    assert store.doc_freq_calls == first_df  # no new DF hit


async def test_cache_miss_new_tokens_refetch_df() -> None:
    """A query with tokens not yet seen re-hits the store for the misses only.

    ``corpus_size`` depends only on the partition scope, so it stays cached
    (same partition → one hit). DF is per-token, so the new terms miss and
    trigger exactly one more DF round-trip.
    """
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)

    await searcher._build_idf("alpha", ["p1"])

    await searcher._build_idf("alpha gamma", ["p1"])

    assert store.corpus_size_calls == 1  # partition scope unchanged → still 1
    assert store.doc_freq_calls == 2  # "gamma" missed → one refetch


# ---------------------------------------------------------------------------
# TTL Expiry
# ---------------------------------------------------------------------------


async def test_ttl_expiry_refetches_after_deadline() -> None:
    """A cached entry that has aged past its TTL becomes a miss and re-fetches."""
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)
    # Make the TTL effectively instantaneous: any second call is past the deadline.
    searcher._idf_cache_ttl = 0.0

    await searcher._build_idf("alpha beta", ["p1"])
    assert store.corpus_size_calls == 1
    assert store.doc_freq_calls == 1

    await searcher._build_idf("alpha beta", ["p1"])

    # With a 0s TTL the prior entries expired, so both stats re-hit the store.
    assert store.corpus_size_calls == 2
    assert store.doc_freq_calls == 2


# ---------------------------------------------------------------------------
# Partition Isolation
# ---------------------------------------------------------------------------


async def test_partition_isolation_does_not_cross_scopes() -> None:
    """Different partition scopes get independent corpus_size entries, and the
    same tokens on a different scope re-fetch DF rather than reuse."""
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)

    await searcher._build_idf("alpha beta", ["p1"])
    first_corpus, first_df = store.corpus_size_calls, store.doc_freq_calls

    # Same tokens, different partition scope → independent entries, so both
    # stats miss and re-fetch; a cached p1 entry must not serve a p2 query.
    await searcher._build_idf("alpha beta", ["p2"])

    assert store.corpus_size_calls == first_corpus + 1
    assert store.doc_freq_calls == first_df + 1

    # Order-independence: a re-scope of the same set as p1 should now hit cache.
    await searcher._build_idf("alpha beta", ["p1"])
    assert store.corpus_size_calls == first_corpus + 1  # p1 still cached → no hit
    assert store.doc_freq_calls == first_df + 1


async def test_df_keyed_by_token_does_not_leak_across_tokens() -> None:
    """DF entries are keyed by token, so one token's df never masquerades as
    another's — observable through IDF: a rare term and a common term on the
    same partition scope keep distinct scores even after caching."""
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)

    idf = await searcher._build_idf("alpha beta", ["p1"])
    assert idf is not None
    rare_score = idf("alpha")  # df 1  → higher IDF
    common_score = idf("beta")  # df 5  → lower IDF
    assert rare_score > common_score

    # Re-querying only the common term must not reuse the rare term's df: its
    # IDF comes from its own cached entry, not alpha's. ``beta`` was already
    # cached by the first query, so the second query adds *no* DF round-trip —
    # and the common score is unchanged (it did not pick up alpha's rare-term df).
    idf_beta_only = await searcher._build_idf("beta", ["p1"])
    assert idf_beta_only is not None
    assert idf_beta_only("beta") == common_score
    assert store.doc_freq_calls == 1  # beta cached from query 1 → no refetch, no leak


@pytest.mark.parametrize("order_a,order_b", [(["p2", "p1"], ["p1", "p2"])])
async def test_partition_key_is_order_independent(order_a: list[str], order_b: list[str]) -> None:
    """The same partition set in any order maps to one cache entry."""
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)

    await searcher._build_idf("alpha", order_a)
    corpus_after_first = store.corpus_size_calls

    await searcher._build_idf("alpha", order_b)

    assert store.corpus_size_calls == corpus_after_first  # same set → hit


async def test_zero_statistics_are_cached() -> None:
    """Zero corpus/DF values are answers, not cache misses."""
    empty_store = _RecordingStore(corpus_size=0)
    empty_searcher = _make_searcher(empty_store)

    assert await empty_searcher._build_idf("alpha", ["p1"]) is None
    assert await empty_searcher._build_idf("alpha", ["p1"]) is None
    assert empty_store.corpus_size_calls == 1
    assert empty_store.doc_freq_calls == 0

    zero_df_store = _RecordingStore(corpus_size=10, df_map={"alpha": 0})
    zero_df_searcher = _make_searcher(zero_df_store)
    assert await zero_df_searcher._build_idf("alpha", ["p1"]) is not None
    assert await zero_df_searcher._build_idf("alpha", ["p1"]) is not None
    assert zero_df_store.corpus_size_calls == 1
    assert zero_df_store.doc_freq_calls == 1


# ---------------------------------------------------------------------------
# Concurrent miss de-duplication (the instance lock around the miss section)
# ---------------------------------------------------------------------------


async def test_concurrent_miss_deduplicates_store_calls() -> None:
    """Concurrent ``_build_idf`` calls that miss the same key share one fetch.

    Without the instance lock guarding the miss → fetch → back-fill section, N
    coroutines entering with the same cold key would each hit the store (N
    round-trips, correct result but wasteful). The leader fetches; waiters
    re-check the cache under the lock and find it populated, so ``corpus_size``
    is called exactly once for the whole concurrent batch, and every caller
    gets the same IDF weighter.
    """
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)

    # Fire 5 identical cold-key calls concurrently. corpus_size depends only on
    # the partition scope, so the leader's single fetch warms it for all 5.
    results = await asyncio.gather(*[searcher._build_idf("alpha", ["p1"]) for _ in range(5)])

    assert store.corpus_size_calls == 1  # leader fetched, the rest hit cache
    # DF is per-token; "alpha" was fetched once by the leader too.
    assert store.doc_freq_calls == 1
    # Every concurrent caller built the same weighter from the shared stats.
    scores = [idf("alpha") for idf in results if idf is not None]
    assert len(scores) == 5
    assert len(set(scores)) == 1


async def test_concurrent_distinct_keys_still_fetch_their_own() -> None:
    """The lock de-duplicates *identical* misses, not unrelated ones.

    Two concurrent calls over disjoint token sets (on the same cached partition)
    share the cached ``corpus_size`` but each fetches its own DF — the lock
    serialises the section but does not collapse distinct keys.
    """
    store = _RecordingStore(corpus_size=100, df_map=_df_map())
    searcher = _make_searcher(store)

    # Warm corpus_size for the partition so only DF is in play.
    await searcher._build_idf("alpha", ["p1"])
    corpus_before = store.corpus_size_calls
    df_before = store.doc_freq_calls

    await asyncio.gather(
        searcher._build_idf("beta", ["p1"]),  # new token → its own DF fetch
        searcher._build_idf("gamma", ["p1"]),  # different new token → its own
    )

    assert store.corpus_size_calls == corpus_before  # partition warmed → 0 more
    assert store.doc_freq_calls == df_before + 2  # beta + gamma, distinct keys
