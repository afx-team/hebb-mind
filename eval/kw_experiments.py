"""Experimental keyword-retrieval variants, swept offline via retrieval_lab.

Lets us A/B FTS query construction + scoring WITHOUT touching production
code, by overriding ``MemorySearcher._keyword_search`` so the rest of the
pipeline (RRF, turn-window expansion, calibrated scoring) is unchanged.

Knobs:
  * synonyms   — OR-expand the built-in synonym groups (current default)
  * phrase     — add exact-phrase + NEAR clauses to lift contiguous matches
  * scorer     — "fts" (native bm25, k1=1.2/b=0.75) | "bm25plus" (tuned)
  * k1/b/delta — BM25+ parameters (short-doc tuning: low b, δ floor)
  * rm3        — pseudo-relevance feedback expansion (no LLM)

Winners get promoted into fts_query.py / sqlite_store.py / searcher.py.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from hebb.models.memory import Memory
from hebb.retrieval.fts_query import _STOPWORDS, _SYNONYM_INDEX, _TOKEN_RE, build_fts_query
from hebb.retrieval.lexical_relevance import _content_tokens, _stem
from hebb.retrieval.searcher import MemorySearcher
from hebb.storage.sqlite_store import _row_to_memory


@dataclass
class KwConfig:
    synonyms: bool = True
    phrase: bool = False
    scorer: str = "fts"        # "fts" | "bm25plus" | "blend"
    k1: float = 0.9
    b: float = 0.4
    delta: float = 1.0
    rm3: bool = False
    rm3_terms: int = 10
    rm3_topdocs: int = 5
    overfetch: int = 60
    # blend: rescore FTS pool by native-BM25 (min-max normalized, correct
    # porter tokenization) boosted by query-term coverage + proximity — the two
    # signals BM25 lacks on short docs. blend = bm25n*(1 + A*cov + B*prox)
    blend_cov: float = 0.6
    blend_prox: float = 0.4

    def tag(self) -> str:
        parts = [self.scorer]
        if self.scorer == "bm25plus":
            parts.append(f"k1{self.k1}b{self.b}d{self.delta}")
        if self.scorer == "blend":
            parts.append(f"cov{self.blend_cov}prox{self.blend_prox}")
        if not self.synonyms:
            parts.append("nosyn")
        if self.phrase:
            parts.append("phrase")
        if self.rm3:
            parts.append(f"rm3-{self.rm3_terms}/{self.rm3_topdocs}")
        return ",".join(parts)


def _query_content_terms(query: str) -> list[str]:
    """Stemmed, stopword-free content terms of the query (for TF/IDF)."""
    out: list[str] = []
    seen: set[str] = set()
    for w in _TOKEN_RE.findall(query.lower()):
        if w.isdigit() or (len(w) > 1 and w not in _STOPWORDS):
            s = w if w.isdigit() else _stem(w)
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _build_match(query: str, cfg: KwConfig) -> str:
    """Construct the FTS5 MATCH expression for this config.

    Base is the production OR-bag (optionally without synonym expansion).
    With phrase=True we prepend exact-phrase and NEAR clauses so contiguous
    query n-grams score higher inside BM25 itself, keeping the OR-bag as the
    recall floor.
    """
    if cfg.synonyms:
        base = build_fts_query(query)
    else:
        # OR-bag of stemmed content terms only, no synonym groups.
        toks = _query_content_terms(query)
        base = " OR ".join(toks)
    if not base:
        return ""

    if not cfg.phrase:
        return base

    # Surface (unstemmed) content tokens for phrase/NEAR clauses.
    surface = [w for w in _TOKEN_RE.findall(query.lower())
               if (len(w) > 1 and w not in _STOPWORDS) or w.isdigit()]
    clauses: list[str] = []
    if len(surface) >= 2:
        # exact contiguous phrase of the whole content-token sequence
        if len(surface) <= 8:
            clauses.append('"' + " ".join(surface) + '"')
        # pairwise NEAR for adjacent content tokens
        for a, b in zip(surface, surface[1:]):
            clauses.append(f'NEAR("{a}" "{b}", 5)')
    clauses.append(base)  # recall floor
    return " OR ".join(f"({c})" for c in clauses)


async def _fts_candidates(store, match_expr: str, partition_ids, limit: int):
    """Run a raw FTS MATCH and return [(memory, bm25_rank_negative)]."""
    if not match_expr:
        return []
    try:
        if partition_ids:
            ph = ",".join("?" * len(partition_ids))
            cur = await store.db.execute(
                f"""SELECT f.memory_id, bm25(memory_fts) AS rank
                    FROM memory_fts f
                    WHERE memory_fts MATCH ? AND f.partition_id IN ({ph})
                    ORDER BY rank LIMIT ?""",
                (match_expr, *partition_ids, limit),
            )
        else:
            cur = await store.db.execute(
                """SELECT f.memory_id, bm25(memory_fts) AS rank
                   FROM memory_fts f WHERE memory_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (match_expr, limit),
            )
    except Exception:
        return []
    rows = list(await cur.fetchall())
    if not rows:
        return []
    ids = [r["memory_id"] for r in rows]
    ph = ",".join("?" * len(ids))
    cur2 = await store.db.execute(f"SELECT * FROM memories WHERE id IN ({ph})", tuple(ids))
    by_id = {r["id"]: _row_to_memory(r) for r in await cur2.fetchall()}
    out = []
    for r in rows:
        m = by_id.get(r["memory_id"])
        if m is not None:
            out.append((m, float(r["rank"])))
    return out


async def _avgdl(store, partition_ids, cache: dict) -> tuple[float, int]:
    """Average doc length (content tokens) + corpus size, cached per store/partition."""
    key = (id(store), tuple(partition_ids or []))
    if key in cache:
        return cache[key]
    if partition_ids:
        ph = ",".join("?" * len(partition_ids))
        cur = await store.db.execute(
            f"SELECT content FROM memory_fts WHERE partition_id IN ({ph})", tuple(partition_ids))
    else:
        cur = await store.db.execute("SELECT content FROM memory_fts")
    rows = await cur.fetchall()
    lengths = [len(_content_tokens(r["content"])) for r in rows]
    n = len(lengths)
    avg = (sum(lengths) / n) if n else 1.0
    cache[key] = (max(avg, 1.0), n)
    return cache[key]


def _bm25plus(query_terms, idf, doc_tokens, avgdl, k1, b, delta) -> float:
    """BM25+ score of one doc for the query (Lv & Zhai 2011 lower-bound)."""
    if not doc_tokens:
        return 0.0
    dl = len(doc_tokens)
    tf: dict[str, int] = {}
    for t in doc_tokens:
        tf[t] = tf.get(t, 0) + 1
    score = 0.0
    norm = k1 * (1 - b + b * dl / avgdl)
    for term in query_terms:
        f = tf.get(term, 0)
        if f == 0:
            continue
        sat = (f * (k1 + 1)) / (f + norm) + delta
        score += idf(term) * sat
    return score


async def exp_keyword_search(store, query, top_k, partition_ids, cfg: KwConfig, cache: dict):
    """Experimental keyword retrieval returning [(Memory, score)] best-first."""
    from hebb.retrieval.lexical_relevance import bm25_idf

    try:
        match = _build_match(query, cfg)
    except Exception:
        match = build_fts_query(query)
    candidates = await _fts_candidates(store, match, partition_ids, cfg.overfetch)
    if not candidates and cfg.phrase:
        # phrase/NEAR expr may be invalid for an edge query — fall back to OR-bag
        candidates = await _fts_candidates(store, build_fts_query(query), partition_ids, cfg.overfetch)
    if not candidates:
        return []

    # Optional RM3 PRF: harvest top high-IDF terms from the top docs, OR them in.
    if cfg.rm3:
        avgdl, n = await _avgdl(store, partition_ids, cache)
        term_w: dict[str, float] = {}
        for mem, _ in candidates[: cfg.rm3_topdocs]:
            for t in set(_content_tokens(mem.content)):
                df = await _term_df(store, t, partition_ids)
                term_w[t] = term_w.get(t, 0.0) + bm25_idf(df, n)
        extra = sorted(term_w, key=term_w.get, reverse=True)[: cfg.rm3_terms]
        if extra:
            base = _build_match(query, cfg)
            match2 = base + " OR " + " OR ".join(f'"{t}"' for t in extra if '"' not in t)
            candidates = await _fts_candidates(store, match2, partition_ids, cfg.overfetch) or candidates

    if cfg.scorer == "fts":
        # Native bm25 (rank ascending = best). Convert to descending score.
        return [(m, 1.0 / (1.0 + abs(rank))) for m, rank in candidates]

    if cfg.scorer == "blend":
        # Native-BM25 backbone (correct porter tokenization) min-max normalized
        # within the pool, boosted by the two signals BM25 lacks on short docs:
        #   coverage  = fraction of distinct query content terms present
        #   proximity = tightness of the smallest window covering matched terms
        from hebb.retrieval.lexical_relevance import _min_cover_span

        qterms = _query_content_terms(query)
        nq = len(qterms) or 1
        # Backbone = |bm25| magnitude min-max (sqlite bm25 is negative-better, so
        # abs = larger-better). Magnitude (not rank position) is essential: it
        # preserves the true #1's lead so coverage/proximity can't easily flip it.
        ranks = [abs(rank) for _, rank in candidates]
        lo, hi = min(ranks), max(ranks)
        span = (hi - lo) or 1.0
        scored = []
        for (mem, rank) in candidates:
            bm25n = (abs(rank) - lo) / span
            toks = _content_tokens(mem.content)
            positions: dict[str, list[int]] = {}
            for i, t in enumerate(toks):
                positions.setdefault(t, []).append(i)
            matched = [positions[t] for t in qterms if t in positions]
            cov = len(matched) / nq
            if len(matched) >= 2:
                sp = _min_cover_span(matched)
                ideal = len(matched) - 1
                prox = 1.0 if sp <= ideal else ideal / sp
            else:
                prox = 0.0
            blended = bm25n * (1.0 + cfg.blend_cov * cov + cfg.blend_prox * prox)
            scored.append((mem, blended))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # bm25plus rescoring
    avgdl, n = await _avgdl(store, partition_ids, cache)
    qterms = _query_content_terms(query)
    df_cache: dict[str, int] = {}
    for t in qterms:
        df_cache[t] = await _term_df(store, t, partition_ids)

    def idf(t: str) -> float:
        return bm25_idf(df_cache.get(t, 1), n)

    scored = []
    for mem, _ in candidates:
        s = _bm25plus(qterms, idf, _content_tokens(mem.content), avgdl, cfg.k1, cfg.b, cfg.delta)
        scored.append((mem, s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


async def _term_df(store, term: str, partition_ids) -> int:
    safe = term.replace('"', "")
    if not safe:
        return 0
    try:
        if partition_ids:
            ph = ",".join("?" * len(partition_ids))
            cur = await store.db.execute(
                f'SELECT count(*) FROM memory_fts WHERE memory_fts MATCH ? AND partition_id IN ({ph})',
                (f'"{safe}"', *partition_ids))
        else:
            cur = await store.db.execute(
                'SELECT count(*) FROM memory_fts WHERE memory_fts MATCH ?', (f'"{safe}"',))
        row = await cur.fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


class LabSearcher(MemorySearcher):
    """MemorySearcher whose keyword channel uses the experimental config."""

    def __init__(self, *args, kw_cfg: KwConfig | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kw_cfg = kw_cfg or KwConfig()
        self._lab_cache: dict = {}

    async def _keyword_search(self, query, top_k, partition_ids):
        return await exp_keyword_search(
            self.store, query, top_k, partition_ids, self.kw_cfg, self._lab_cache)
