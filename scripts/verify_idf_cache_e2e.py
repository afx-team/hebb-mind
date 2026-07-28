"""End-to-end verification of the IDF cache via the real HebbMind facade (issue #54).

Unlike ``verify_idf_cache_real_store.py`` (which drives ``SQLiteMemoryStore`` +
``MemorySearcher`` directly), this starts the actual public SDK entrypoint —
``HebbMind`` — exactly the way README's five-minute tour does: ``hc.add(...)``
then ``hc.search(...)``. The whole stack (storage + embedder + graph + hybrid
searcher) runs in-process; only the embedding model is swapped for the noop
provider so no model download / GPU is needed.

Asserts, against the genuine component chain:

1. After two identical ``search()`` calls, the searcher's IDF statistic caches
   are populated (corpus_size: one entry per partition scope; df: one per
   (token, partition)) — i.e. the production code path actually fills the cache.
2. The second ``search()`` reuses cached stats — verified by counting real
   ``SQLiteMemoryStore`` method calls (each = a real SQL round-trip).
3. Staleness is bounded, not silent: a memory written AFTER the cache is filled
   is invisible to IDF within the TTL (expected by design), and reappears once
   the TTL elapses. Proves the cache is honest about its trade-off.

Runnable script (scripts/ is ruff-excluded), prints PASS/FAIL, exits non-zero
on regression.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hebb import HebbMind
from hebb.config.settings import Settings
from hebb.storage.sqlite_store import SQLiteMemoryStore

_QUERY = "alpha beta"


class IDFReadCounter:
    """Count real calls to the live store's IDF-read methods."""

    def __init__(self, store: SQLiteMemoryStore) -> None:
        self.corpus = 0
        self.df = 0
        self._store = store
        self._orig_c = store.corpus_size
        self._orig_d = store.keyword_doc_freqs
        store.corpus_size = self._c  # type: ignore[method-assign]
        store.keyword_doc_freqs = self._d  # type: ignore[method-assign]

    async def _c(self, partition_ids=None) -> int:
        self.corpus += 1
        return await self._orig_c(partition_ids)

    async def _d(self, terms, partition_ids=None) -> dict[str, int]:
        self.df += 1
        return await self._orig_d(terms, partition_ids)


def main() -> int:
    failures: list[str] = []
    home = Path(tempfile.mkdtemp())
    settings = Settings(
        home_dir=home,
        llm_model="openai/gpt-4o-mini",
        embedding_provider="noop",
        embedding_dim=3,
    )

    with HebbMind(config=settings) as hc:
        hc.add("alpha beta rule the early corpus", partition="mem_semantic")
        hc.add("beta dominates the common terms here", partition="mem_semantic")

        searcher = hc._searcher  # the live MemorySearcher the facade owns
        store = searcher.store  # type: ignore[assignment]
        counter = IDFReadCounter(store)

        # ---- Check 1: two identical searches, second reuses the cache ------- #
        hc.search(_QUERY)
        first_c, first_d = counter.corpus, counter.df
        hc.search(_QUERY)
        second_c, second_d = counter.corpus, counter.df
        d_c, d_d = second_c - first_c, second_d - first_d

        cache_populated = len(searcher._corpus_size_cache) >= 1 and len(searcher._df_cache) >= 1
        second_reused = d_c == 0 and d_d == 0
        print(
            "Check 1 — real HebbMind.search() twice:\n"
            f"  caches populated? corpus_size={len(searcher._corpus_size_cache)}, df={len(searcher._df_cache)}\n"
            f"  1st → {first_c} corpus / {first_d} df calls;  2nd → +{d_c} / +{d_d}  (expect 0/0)"
        )
        if not cache_populated:
            failures.append("Check 1a: production path did not populate the IDF cache.")
        if not second_reused:
            failures.append(f"Check 1b: 2nd search added {d_c}/{d_d} IDF calls (expected 0/0).")

        # ---- Check 2: staleness within TTL, then self-heals after TTL ------- #
        # Write a 3rd memory. Within the TTL the cached corpus_size is stale
        # (still 2), so the IDF weighter keeps using the old N — by design.
        hc.add("gamma is a rare word", partition="mem_semantic")
        # Read the ACTUAL partition key the production path cached under (the
        # facade's search scope may be None or a partition set — don't assume).
        pk = next(iter(searcher._corpus_size_cache.keys()))
        cached_n = searcher._idf_corpus_size_get(time.monotonic(), pk)
        stale_within_ttl = cached_n == 2  # real is now 3
        print(
            f"\nCheck 2 — staleness bounded by TTL:\n"
            f"  after 3rd write, cached corpus_size = {cached_n} (real 3) → stale within TTL? {stale_within_ttl}"
        )
        if not stale_within_ttl:
            failures.append("Check 2a: cache did not show expected bounded staleness.")

        # Backdate the cache entry so the TTL elapses, then search → must
        # refetch the NEW corpus size (3).
        entry = searcher._corpus_size_cache.get(pk)
        if entry is not None:
            searcher._corpus_size_cache[pk] = (entry[0], time.monotonic() - 1)
        # Also expire the df entries so they refetch against the new corpus.
        for k in list(searcher._df_cache.keys()):
            v = searcher._df_cache[k]
            searcher._df_cache[k] = (v[0], time.monotonic() - 1)
        counter.corpus = 0
        hc.search("alpha gamma")  # gamma is the newly-added token
        refreshed = searcher._idf_corpus_size_get(time.monotonic(), pk)
        refetched = refreshed == 3
        print(f"  after forced TTL expiry + search, refetched corpus_size = {refreshed} (expect 3) → self-healed? {refetched}")
        if not refetched:
            failures.append("Check 2b: cache did not refetch the new corpus_size after TTL expiry.")

    print()
    if failures:
        print("RESULT: FAIL — " + " | ".join(failures))
        return 1
    print("RESULT: PASS — real HebbMind facade fills/reuses/heals the IDF cache end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())