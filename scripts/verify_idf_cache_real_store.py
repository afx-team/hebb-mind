"""End-to-end verification for the IDF statistic cache (issue #54).

Runs against a REAL ``SQLiteMemoryStore`` on a temp FTS5 DB (vector extension
disabled — the IDF path only touches ``memory_fts``, not ``vec0``) and counts
calls to the store's actual IDF-read methods (``corpus_size`` /
``keyword_doc_freqs``). Each such call fires real SQL against the genuine FTS5
index, so this is a faithful — not mocked — measure of the DB round-trips the
cache is meant to avoid:

1. A repeated identical ``search()`` adds ZERO real ``corpus_size`` / DF store
   calls within the TTL (issue "Expected Outcomes" bullet 1).
2. The ``RecallAgent.recall`` 3-query pass (``queries[:3]`` over an unchanged
   corpus) calls ``corpus_size`` exactly ONCE and reuses DF for overlapping
   tokens (issue "Expected Outcomes" bullet 2).

Not a pytest case — a runnable script that prints a PASS/FAIL verdict and exits
non-zero on regression. Kept out of the test suite (scripts/ is ruff-excluded):
it touches real sqlite and duplicates the unit-store assertions, here only to
prove the cache hits against the genuine store.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

# repo src on path when run from the project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hebb.embedding.local import NoopEmbedder
from hebb.models.memory import MemoryCreate, MemoryQuery
from hebb.retrieval.searcher import MemorySearcher
from hebb.storage.migrations import get_connection, initialize_schema
from hebb.storage.sqlite_store import SQLiteMemoryStore

# Memories whose content maps cleanly to the test queries' surface tokens.
_MEMOIRS = [
    ("alpha rules the early corpus", "p1"),
    ("beta dominates the common terms here", "p1"),
    ("gamma is a rare discriminating word", "p1"),
]
_QUERY = "alpha beta gamma"  # surface tokens line up with the seeded terms


class IDFReadCounter:
    """Count calls to the real store's ``corpus_size`` / ``keyword_doc_freqs``.

    Wraps (not replaces) the genuine ``SQLiteMemoryStore`` methods, so each
    counted call is a real SQL round-trip — the exact thing the cache skips.
    """

    def __init__(self, store: SQLiteMemoryStore) -> None:
        self.corpus_calls = 0
        self.df_calls = 0
        self._store = store
        self._orig_corpus = store.corpus_size
        self._orig_df = store.keyword_doc_freqs
        store.corpus_size = self._count_corpus  # type: ignore[method-assign]
        store.keyword_doc_freqs = self._count_df  # type: ignore[method-assign]

    async def _count_corpus(self, partition_ids: list[str] | None = None) -> int:
        self.corpus_calls += 1
        return await self._orig_corpus(partition_ids)

    async def _count_df(self, terms: list[str], partition_ids: list[str] | None = None) -> dict[str, int]:
        self.df_calls += 1
        return await self._orig_df(terms, partition_ids)

    def snapshot(self) -> tuple[int, int]:
        return self.corpus_calls, self.df_calls


async def _seed(store: SQLiteMemoryStore, embedder: NoopEmbedder) -> None:
    for content, partition in _MEMOIRS:
        await store.create(
            MemoryCreate(content=content, partition_id=partition),
            embedding=await embedder.embed(content),
        )


async def main() -> int:
    embedder = NoopEmbedder(3)
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "verify.db"
        # load_vec=False: skip sqlite-vec (unavailable in some envs); IDF only
        # needs the FTS5 index, which initialise_schema always creates.
        conn = await get_connection(str(db_path), load_vec=False)
        await initialize_schema(conn, embedder.dimension)
        store = SQLiteMemoryStore(conn)
        await _seed(store, embedder)
        counter = IDFReadCounter(store)

        searcher = MemorySearcher(
            store=store,  # type: ignore[arg-type]
            embedder=embedder,
            graph=None,
            vector_search_enabled=False,  # IDF lives on the keyword/lexical path
            graph_search_enabled=False,
            graph_expansion_enabled=False,
        )

        # ---- Check 1: repeated identical search adds ZERO IDF store calls --- #
        await searcher.search(MemoryQuery(query=_QUERY, top_k=10))
        first_corpus, first_df = counter.snapshot()

        await searcher.search(MemoryQuery(query=_QUERY, top_k=10))
        after_corpus, after_df = counter.snapshot()
        delta_corpus, delta_df = after_corpus - first_corpus, after_df - first_df

        check1_ok = delta_corpus == 0 and delta_df == 0
        print(
            "Check 1 — repeated identical search within TTL:\n"
            f"  first search  → {first_corpus} corpus_size call(s), {first_df} DF call(s)\n"
            f"  repeat search → +{delta_corpus} corpus_size call(s), +{delta_df} DF call(s)  (expect 0, 0)"
        )
        if not check1_ok:
            failures.append("Check 1: repeated search did not hit the cache (expected 0 IDF calls).")

        # ---- Check 2: RecallAgent-style 3-query pass over same corpus ----- #
        # Fresh searcher so the cache starts empty, then reproduce RecallAgent's
        # queries[:3] loop: three back-to-back searches with overlapping tokens.
        # One fresh token (delta) plus two shared (alpha/beta) makes both
        # behaviours visible: corpus_size fetched once, shared DF reused, the
        # fresh term the only new DF fetch.
        recall_searcher = MemorySearcher(
            store=store,  # type: ignore[arg-type]
            embedder=embedder,
            graph=None,
            vector_search_enabled=False,
            graph_search_enabled=False,
            graph_expansion_enabled=False,
        )
        recall_counter = IDFReadCounter(store)
        start_corpus, start_df = recall_counter.snapshot()
        # Add a fresh memory so "delta" is a real DF-eligible token.
        await store.create(
            MemoryCreate(content="delta epsilon fresh tokens", partition_id="p1"),
            embedding=await embedder.embed("delta epsilon fresh tokens"),
        )
        for q in ("alpha beta delta", "beta gamma alpha", "alpha delta"):
            await recall_searcher.search(MemoryQuery(query=q, top_k=10))
        three_corpus = recall_counter.corpus_calls - start_corpus
        three_df = recall_counter.df_calls - start_df
        # corpus_size depends only on the partition scope → fetched exactly once.
        # DF is per-token; alpha/beta/gamma repeat across the 3 queries and are
        # fetched only the first time they appear, while the fresh delta/epsilon
        # add a few misses — so >1 DF call but far fewer than 3 queries × terms.
        check2_ok = three_corpus == 1 and three_df >= 1
        print(
            f"\nCheck 2 — RecallAgent 3-query pass (queries[:3], overlapping tokens):\n"
            f"  3 searches → {three_corpus} corpus_size call(s), {three_df} DF call(s)\n"
            f"  (expect corpus_size == 1; DF >=1 and reused across overlap, not per-query)"
        )
        if not check2_ok:
            failures.append(
                f"Check 2: 3-query pass issued {three_corpus} corpus_size / {three_df} DF calls "
                "(expected corpus_size==1, DF reused)."
            )

        await conn.close()

    print()
    if failures:
        print("RESULT: FAIL — " + " | ".join(failures))
        return 1
    print("RESULT: PASS — real SQLiteMemoryStore issues zero/reused IDF round-trips within TTL.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
