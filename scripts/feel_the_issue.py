"""Feel-the-issue demo for #54 — show the IDF cache's real DB impact.

Runs the SAME search workload twice against a real HebbMind + SQLiteMemoryStore:

  A) With the cache (default).
  B) With the cache neutralised (TTL=0, so every call re-fetches).

and prints the number of real ``corpus_size`` / ``keyword_doc_freqs`` DB calls
in each case. That delta is the work issue #54 removes — made visible, not
asserted. Intended for a human to read the output, so it narrates as it goes.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hebb import HebbMind
from hebb.config.settings import Settings
from hebb.storage.sqlite_store import SQLiteMemoryStore

# A realistic recall workload: 3 back-to-back queries over one corpus,
# mirroring RecallAgent.recall's queries[:3] loop. The queries share words
# ("python", "retrieval") so the cache can reuse DF across them — the exact
# case issue #54 calls out.
QUERIES = [
    "how does python handle concurrency and the gil",
    "python gil and retrieval tradeoffs",
    "python async retrieval patterns",
]


class Counter:
    def __init__(self, store: SQLiteMemoryStore) -> None:
        self.corpus = 0
        self.df = 0
        self._s = store
        self._oc = store.corpus_size
        self._od = store.keyword_doc_freqs
        store.corpus_size = self._c  # type: ignore[method-assign]
        store.keyword_doc_freqs = self._d  # type: ignore[method-assign]

    async def _c(self, partition_ids=None) -> int:
        self.corpus += 1
        return await self._oc(partition_ids)

    async def _d(self, terms, partition_ids=None) -> dict[str, int]:
        self.df += 1
        return await self._od(terms, partition_ids)


def _seed(hc: HebbMind) -> None:
    hc.add("Python's GIL serializes bytecode execution in one process.", partition="mem_semantic")
    hc.add("RAG retrieves documents then conditions the LLM on them.", partition="mem_semantic")
    hc.add("asyncio lets Python do concurrent IO despite the GIL.", partition="mem_semantic")
    hc.add("I prefer dark mode and 2-space indents.", partition="mem_preference")


def _run_workload(hc: HebbMind) -> tuple[int, int]:
    store = hc._searcher.store  # type: ignore[assignment]
    c = Counter(store)
    # Scenario 1: RecallAgent's 3-query pass (overlapping tokens).
    for q in QUERIES:
        hc.search(q)
    # Scenario 2: the same query retried 4 times (UI retry / agent retry) —
    # the other case issue #54 names. With the cache, only the first hits.
    for _ in range(4):
        hc.search("python gil retrieval")
    return c.corpus, c.df


def _new_home() -> Path:
    home = Path(tempfile.mkdtemp())
    return home


def main() -> int:
    print("=" * 64)
    print("Issue #54 demo: does caching cut DB round-trips on recall?")
    print("=" * 64)

    # ---- A) With cache (default, TTL=60s) ------------------------------- #
    print("\n[A] WITH cache (TTL=60s, the fix):")
    home_a = _new_home()
    sa = Settings(home_dir=home_a, llm_model="openai/gpt-4o-mini",
                  embedding_provider="noop", embedding_dim=3)
    hc = HebbMind(config=sa)
    _seed(hc)
    corpus_a, df_a = _run_workload(hc)
    print(f"    3 recall queries + 4 retried same-query searches")
    print(f"      → {corpus_a} corpus_size SQL, {df_a} DF SQL")
    hc.close()
    shutil.rmtree(home_a, ignore_errors=True)

    # ---- B) Without cache (TTL=0 → every call re-fetches) --------------- #
    print("\n[B] WITHOUT cache (TTL=0 → re-fetch every time):")
    home_b = _new_home()
    sb = Settings(home_dir=home_b, llm_model="openai/gpt-4o-mini",
                  embedding_provider="noop", embedding_dim=3)
    hc = HebbMind(config=sb)
    _seed(hc)
    hc._searcher._idf_cache_ttl = 0.0  # neutralise: all entries expire instantly
    corpus_b, df_b = _run_workload(hc)
    print(f"    3 recall queries + 4 retried same-query searches")
    print(f"      → {corpus_b} corpus_size SQL, {df_b} DF SQL")
    hc.close()
    shutil.rmtree(home_b, ignore_errors=True)

    # ---- Verdict -------------------------------------------------------- #
    print("\n" + "=" * 64)
    print("VERDICT")
    print("=" * 64)
    print(f"  corpus_size SQL:  with cache {corpus_a}  vs  without {corpus_b}")
    print(f"  DF SQL:           with cache {df_a}  vs  without {df_b}")
    saved_c = corpus_b - corpus_a
    saved_d = df_b - df_a
    print(f"\n  #54 saves {saved_c} corpus_size round-trip(s) and {saved_d} DF round-trip(s)")
    print("  on this 3-query recall pass. That is the waste the cache removes.")
    print("=" * 64)
    return 0 if (saved_c >= 0 and saved_d >= 0) else 1


if __name__ == "__main__":
    sys.exit(main())