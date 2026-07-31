"""Offline threshold calibration probe for the strict-recall floor.

Measures Recall@k and empty-recall fraction across a grid of
``(min_score, rerank_floor_ratio)`` values so the shipped defaults
(0.8 / 0.625) can be validated — or retuned — against a labelled
retrieval dataset.

Core idea: run retrieval ONCE per query with ``min_score=0`` (no floor)
and a real cross-encoder reranker, collect every result with its
post-rerank score, then post-filter for each parameter combination.
The expensive step (retrieval + rerank) happens once; the parameter
sweep is pure post-processing.

Run:
  python -m eval.threshold_probe
  python -m eval.threshold_probe --rerank --output eval/reports/threshold_calibration.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import hebb.storage._sqlite_compat  # noqa: F401  patch sqlite3 -> pysqlite3 for vec0
import aiosqlite

from eval.datasets.locomo import LoCoMoAdapter
from hebb.models.memory import MemoryCreate, MemoryMetadata, MemoryQuery
from hebb.retrieval.searcher import MemorySearcher
from hebb.storage.migrations import get_connection, initialize_schema
from hebb.storage.sqlite_store import SQLiteMemoryStore

logging.disable(logging.WARNING)

# ──────────────────────────────────────────────────────────────────────
# Data classes (mirrors retrieval_lab.py)
# ──────────────────────────────────────────────────────────────────────

_MIN_CONTENT_LEN = 20
_DIA_RE = re.compile(r"^\s*D\s*(\d+)\s*:\s*\d+\s*$", re.IGNORECASE)


@dataclass
class Doc:
    content: str
    metadata: dict


@dataclass
class Q:
    qid: str
    text: str
    relevant: set[str]  # gold session ids
    category: str = ""


@dataclass
class Unit:
    pid: str
    docs: list[Doc] = field(default_factory=list)
    questions: list[Q] = field(default_factory=list)


@dataclass
class ResultEntry:
    """One retrieved result, before any floor filtering."""
    score: float
    composite_score: float  # pre-rerank composite (same as score when no reranker)
    session_id: str | None
    is_reranked: bool


@dataclass
class QueryRecord:
    """Full retrieval output for a single query."""
    qid: str
    question: str
    relevant: set[str]
    category: str
    results: list[ResultEntry]
    reranked_count: int


# ──────────────────────────────────────────────────────────────────────
# Null embedder (vector path disabled)
# ──────────────────────────────────────────────────────────────────────


class NullEmbedder:
    @property
    def dimension(self) -> int:
        return 384

    async def embed(self, text: str) -> list[float]:
        return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


# ──────────────────────────────────────────────────────────────────────
# Data loading — LoCoMo
# ──────────────────────────────────────────────────────────────────────


def _load_locomo() -> list[Unit]:
    adapter = LoCoMoAdapter()
    scenarios = adapter.load(Path("eval/data/locomo/locomo10.json"))
    unit = Unit(pid="mem_hippocampus")
    for sc in scenarios:
        turns = sorted(sc.conversations, key=lambda t: t.turn_index or 0)
        seen: dict[str | None, set[str]] = {}
        for t in turns:
            c = (t.content or "").strip()
            if len(c) < _MIN_CONTENT_LEN:
                continue
            b = seen.setdefault(t.session_id, set())
            d = hashlib.sha256(c.lower().encode()).hexdigest()
            if d in b:
                continue
            b.add(d)
            md: dict = {}
            if t.session_id is not None:
                md["session_id"] = str(t.session_id)
            if t.turn_index is not None:
                md["turn"] = t.turn_index
            if t.timestamp:
                md["timestamp"] = t.timestamp
            unit.docs.append(Doc(c[:10000], md))
        # per-pair
        for i in range(0, len(turns) - 1, 2):
            t1, t2 = turns[i], turns[i + 1]
            left = (t1.content or "").strip()
            right = (t2.content or "").strip()
            if not left and not right:
                continue
            lines = []
            if t1.timestamp:
                lines.append(f"[{t1.timestamp}]")
            if left:
                lines.append(f"[{t1.role}] {left}")
            if right:
                lines.append(f"[{t2.role}] {right}")
            summary = "\n".join(lines)
            if len(summary) < _MIN_CONTENT_LEN:
                continue
            md = {}
            if t1.session_id is not None:
                md["session_id"] = str(t1.session_id)
            if t1.timestamp:
                md["timestamp"] = t1.timestamp
            md["turn_pair"] = [t1.turn_index, t2.turn_index]
            unit.docs.append(Doc(summary[:10000], md))
        # questions
        for q in sc.questions:
            ev = q.evidence or []
            sessions: set[str] = set()
            for e in ev:
                if e is None:
                    continue
                m = _DIA_RE.match(str(e))
                if m:
                    sessions.add(m.group(1))
            if not sessions or not (q.question or "").strip():
                continue
            unit.questions.append(Q(q.question_id, q.question, sessions, q.category))
    return [unit]


# ──────────────────────────────────────────────────────────────────────
# Store + searcher construction
# ──────────────────────────────────────────────────────────────────────


async def _build_store(unit: Unit, embedder) -> tuple[SQLiteMemoryStore, aiosqlite.Connection]:
    use_vec = embedder is not None
    db = await get_connection(":memory:", load_vec=use_vec)
    await initialize_schema(db, embedding_dim=(embedder.dimension if use_vec else 384),
                            create_vec_table=use_vec)
    store = SQLiteMemoryStore(db)
    embs = await embedder.embed_batch([d.content for d in unit.docs]) if use_vec else None
    for i, d in enumerate(unit.docs):
        await store.create(
            MemoryCreate(content=d.content, partition_id=unit.pid, importance_score=5.0,
                         tags=["lab"], metadata=MemoryMetadata(**d.metadata), source="lab"),
            embedding=embs[i] if embs else None,
        )
    return store, db


_RERANKER = None


def _get_reranker(model: str, top_n: int):
    global _RERANKER
    if _RERANKER is None:
        from hebb.retrieval.rerank.local import LocalReranker
        _RERANKER = LocalReranker(model_name=model, top_n=top_n)
    return _RERANKER


def _make_searcher(store, embedder, skw, reranker=None):
    return MemorySearcher(store, embedder or NullEmbedder(), None, reranker, **skw)


# ──────────────────────────────────────────────────────────────────────
# Retrieval: run each query with min_score=0 to get ALL results
# ──────────────────────────────────────────────────────────────────────


async def _collect_query_records(
    searcher: MemorySearcher,
    unit: Unit,
    reranker_top_n: int,
    top_k: int,
    limit: int,
) -> list[QueryRecord]:
    """Run every question with min_score=0 and return unfiltered results."""
    records: list[QueryRecord] = []
    qs = unit.questions[:limit] if limit else unit.questions
    total = len(qs)
    for qi, q in enumerate(qs):
        print(f"\r  collecting query {qi + 1}/{total}...", end="", flush=True)
        mq = MemoryQuery(
            query=q.text,
            top_k=top_k,
            partition_ids=[unit.pid],
            weight_recency=0.0,
            weight_importance=0.0,
            weight_relevance=1.0,
            min_score=0.0,  # no floor — get ALL results
        )
        resp = await searcher.search(mq)
        n_results = len(resp.results)
        rc = min(reranker_top_n, n_results) if searcher.reranker is not None else 0
        entries = []
        for i, r in enumerate(resp.results):
            md = r.memory.metadata.model_dump()
            sid = str(md["session_id"]) if md.get("session_id") is not None else None
            cs = getattr(r, '_pre_rerank_score', r.score)
            entries.append(ResultEntry(
                score=r.score,
                composite_score=cs,
                session_id=sid,
                is_reranked=(i < rc),
            ))
        records.append(QueryRecord(
            qid=q.qid,
            question=q.text,
            relevant=q.relevant,
            category=q.category,
            results=entries,
            reranked_count=rc,
        ))
    print(f"\r  collected {total} queries.           ")
    return records


# ──────────────────────────────────────────────────────────────────────
# Threshold sweep — post-processing
# ──────────────────────────────────────────────────────────────────────


def _apply_floor(
    results: list[ResultEntry],
    reranked_count: int,
    min_score: float,
    ratio: float,
) -> list[ResultEntry]:
    """Replicate searcher.py:284-291 dual-scale floor logic."""
    rerank_floor = min_score * ratio
    kept: list[ResultEntry] = []
    for i, r in enumerate(results):
        floor = rerank_floor if i < reranked_count else min_score
        if r.score >= floor:
            kept.append(r)
    return kept


def _apply_composite_floor(
    results: list[ResultEntry],
    min_score: float,
) -> list[ResultEntry]:
    """Filter by composite score only (ignore sigmoid), single-scale."""
    return [r for r in results if r.composite_score >= min_score]


def _recall_at_k(
    kept: list[ResultEntry],
    relevant: set[str],
    k: int,
) -> bool:
    """True if any of the top-k kept results hits an evidence session."""
    for r in kept[:k]:
        if r.session_id in relevant:
            return True
    return False


@dataclass
class SweepCell:
    min_score: float
    ratio: float
    floor: float  # min_score * ratio (sigmoid floor)
    recall_at: dict[int, float]  # k -> recall
    empty_frac: float
    mean_results: float


def _sweep(
    records: list[QueryRecord],
    min_scores: list[float],
    ratios: list[float],
    ks: list[int],
) -> list[SweepCell]:
    cells: list[SweepCell] = []
    for ms in min_scores:
        for ratio in ratios:
            recalls: dict[int, int] = {k: 0 for k in ks}
            empty = 0
            total_results = 0
            n = len(records)
            for rec in records:
                kept = _apply_floor(rec.results, rec.reranked_count, ms, ratio)
                total_results += len(kept)
                if not kept:
                    empty += 1
                for k in ks:
                    if _recall_at_k(kept, rec.relevant, k):
                        recalls[k] += 1
            cells.append(SweepCell(
                min_score=ms,
                ratio=ratio,
                floor=ms * ratio,
                recall_at={k: recalls[k] / n if n else 0.0 for k in ks},
                empty_frac=empty / n if n else 0.0,
                mean_results=total_results / n if n else 0.0,
            ))
    return cells


def _sweep_composite(
    records: list[QueryRecord],
    min_scores: list[float],
    ks: list[int],
) -> list[SweepCell]:
    """Sweep min_score using composite score for filtering (single-scale)."""
    cells: list[SweepCell] = []
    for ms in min_scores:
        recalls: dict[int, int] = {k: 0 for k in ks}
        empty = 0
        total_results = 0
        n = len(records)
        for rec in records:
            kept = _apply_composite_floor(rec.results, ms)
            total_results += len(kept)
            if not kept:
                empty += 1
            for k in ks:
                if _recall_at_k(kept, rec.relevant, k):
                    recalls[k] += 1
        cells.append(SweepCell(
            min_score=ms,
            ratio=1.0,
            floor=ms,
            recall_at={k: recalls[k] / n if n else 0.0 for k in ks},
            empty_frac=empty / n if n else 0.0,
            mean_results=total_results / n if n else 0.0,
        ))
    return cells


def _compute_baseline(records: list[QueryRecord], ks: list[int]) -> dict[str, float]:
    """Compute Recall@k with no floor (all results kept) as a baseline."""
    recalls: dict[int, int] = {k: 0 for k in ks}
    n = len(records)
    for rec in records:
        for k in ks:
            if _recall_at_k(rec.results, rec.relevant, k):
                recalls[k] += 1
    return {f"R@{k}": recalls[k] / n if n else 0.0 for k in ks}


# ──────────────────────────────────────────────────────────────────────
# Score distribution analysis
# ──────────────────────────────────────────────────────────────────────


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs2 = sorted(xs)
    idx = int(p * (len(xs2) - 1))
    return xs2[idx]


@dataclass
class DistStats:
    n: int
    mean: float
    p10: float
    p50: float
    p90: float
    min_val: float
    max_val: float

    def to_dict(self) -> dict:
        return {
            "n": self.n, "mean": round(self.mean, 4),
            "p10": round(self.p10, 4), "p50": round(self.p50, 4),
            "p90": round(self.p90, 4), "min": round(self.min_val, 4),
            "max": round(self.max_val, 4),
        }


def _dist_stats(xs: list[float]) -> DistStats:
    if not xs:
        return DistStats(0, 0, 0, 0, 0, 0, 0)
    return DistStats(
        n=len(xs),
        mean=sum(xs) / len(xs),
        p10=_percentile(xs, 0.1),
        p50=_percentile(xs, 0.5),
        p90=_percentile(xs, 0.9),
        min_val=min(xs),
        max_val=max(xs),
    )


@dataclass
class ScoreDistributions:
    sigmoid_pool: DistStats
    composite_tail: DistStats
    relevant_sigmoid: DistStats
    irrelevant_sigmoid: DistStats

    def to_dict(self) -> dict:
        return {
            "sigmoid_pool": self.sigmoid_pool.to_dict(),
            "composite_tail": self.composite_tail.to_dict(),
            "relevant_sigmoid": self.relevant_sigmoid.to_dict(),
            "irrelevant_sigmoid": self.irrelevant_sigmoid.to_dict(),
        }


def _score_distributions(records: list[QueryRecord]) -> ScoreDistributions:
    sig_scores: list[float] = []
    comp_scores: list[float] = []
    rel_sig: list[float] = []
    irr_sig: list[float] = []
    for rec in records:
        for r in rec.results:
            if r.is_reranked:
                sig_scores.append(r.score)
                if r.session_id in rec.relevant:
                    rel_sig.append(r.score)
                else:
                    irr_sig.append(r.score)
            else:
                comp_scores.append(r.score)
    return ScoreDistributions(
        sigmoid_pool=_dist_stats(sig_scores),
        composite_tail=_dist_stats(comp_scores),
        relevant_sigmoid=_dist_stats(rel_sig),
        irrelevant_sigmoid=_dist_stats(irr_sig),
    )


# ──────────────────────────────────────────────────────────────────────
# Terminal output
# ──────────────────────────────────────────────────────────────────────


def _print_header(config: dict, n_queries: int) -> None:
    print("\n" + "=" * 72)
    print("  Threshold Calibration Probe")
    print("=" * 72)
    rerank_str = config.get("reranker", "none")
    print(f"  dataset={config['dataset']}  reranker={rerank_str}  "
          f"top_n={config['top_n']}  queries={n_queries}  top_k={config['top_k']}")


def _print_distributions(dist: ScoreDistributions) -> None:
    print("\n--- Score Distributions ---")
    header = f"  {'':20s} {'n':>6s} {'mean':>7s} {'p10':>7s} {'p50':>7s} {'p90':>7s} {'min':>7s} {'max':>7s}"
    print(header)

    def _row(label: str, s: DistStats) -> None:
        print(f"  {label:20s} {s.n:6d} {s.mean:7.3f} {s.p10:7.3f} {s.p50:7.3f} {s.p90:7.3f} {s.min_val:7.3f} {s.max_val:7.3f}")

    _row("Sigmoid pool", dist.sigmoid_pool)
    _row("Composite tail", dist.composite_tail)
    _row("Relevant (sigmoid)", dist.relevant_sigmoid)
    _row("Irrelevant (sigmoid)", dist.irrelevant_sigmoid)


def _print_sweep(cells: list[SweepCell], ks: list[int], current_ms: float, current_ratio: float) -> None:
    k = max(ks)
    rk_label = f"R@{k}"
    print(f"\n--- Threshold Sweep: Recall@{k} ---")
    print(f"  {'min_score':>9s} {'ratio':>7s} {'floor*':>7s} {rk_label:>7s} {'empty%':>7s} {'mean_n':>7s}")
    print(f"  {'':->9s} {'':->7s} {'':->7s} {'':->7s} {'':->7s} {'':->7s}")

    for c in cells:
        marker = "  <-- current" if (
            abs(c.min_score - current_ms) < 1e-6 and abs(c.ratio - current_ratio) < 1e-6
        ) else ""
        print(f"  {c.min_score:9.2f} {c.ratio:7.3f} {c.floor:7.3f} "
              f"{c.recall_at[k]:7.3f} {c.empty_frac * 100:6.1f}% {c.mean_results:7.1f}{marker}")

    print(f"\n  * floor = min_score x ratio (sigmoid pool threshold)")


def _print_recommendation(
    cells: list[SweepCell],
    ks: list[int],
    current_ms: float,
    current_ratio: float,
) -> dict:
    k = max(ks)
    # Find current default
    current = next(
        (c for c in cells if abs(c.min_score - current_ms) < 1e-6 and abs(c.ratio - current_ratio) < 1e-6),
        None,
    )
    # Primary: R@k >= 0.90 and empty_frac < 5%, then highest R@k, then highest min_score
    candidates = [c for c in cells if c.recall_at[k] >= 0.90 and c.empty_frac < 0.05]
    best = None
    strategy = "primary"
    if candidates:
        best = max(candidates, key=lambda c: (c.recall_at[k], c.min_score))
    else:
        # Fallback: minimize empty_frac, then maximize R@k
        non_empty = [c for c in cells if c.empty_frac > 0.0]
        if non_empty:
            min_emp = min(c.empty_frac for c in non_empty)
            fallback_pool = [c for c in non_empty if c.empty_frac <= min_emp + 0.02]
            best = max(fallback_pool, key=lambda c: (c.recall_at[k], c.min_score))
            strategy = "fallback"

    print("\n--- Recommendation ---")
    if best:
        tag = f"R@{k} >= 0.90, empty < 5%" if strategy == "primary" else f"fallback (min empty_frac)"
        print(f"  Best ({tag}): "
              f"min_score={best.min_score:.2f}, ratio={best.ratio:.3f} "
              f"-> R@{k}={best.recall_at[k]:.3f}, empty={best.empty_frac:.1%}")
    else:
        print(f"  No parameter pair meets any recommendation criteria")

    if current:
        print(f"  Current default: min_score={current.min_score:.2f}, ratio={current.ratio:.3f} "
              f"-> R@{k}={current.recall_at[k]:.3f}, empty={current.empty_frac:.1%}")
        if best and current:
            delta_r = best.recall_at[k] - current.recall_at[k]
            delta_e = current.empty_frac - best.empty_frac
            print(f"  Delta: R@{k} {delta_r:+.3f}, empty_frac {delta_e:+.1%}")

    rec = {"strategy": strategy} if best else {}
    if best:
        rec.update({"min_score": best.min_score, "ratio": best.ratio,
                     f"R@{k}": best.recall_at[k], "empty_frac": best.empty_frac})
    return rec


# ──────────────────────────────────────────────────────────────────────
# JSON output
# ──────────────────────────────────────────────────────────────────────


def _save_json(
    path: Path,
    config: dict,
    dists: ScoreDistributions,
    cells: list[SweepCell],
    ks: list[int],
    recommendation: dict,
    current_ms: float,
    current_ratio: float,
    baseline: dict[str, float] | None = None,
) -> None:
    k = max(ks)
    current = next(
        (c for c in cells if abs(c.min_score - current_ms) < 1e-6 and abs(c.ratio - current_ratio) < 1e-6),
        None,
    )
    report = {
        "config": config,
        "score_distributions": dists.to_dict(),
        "baseline": baseline or {},
        "sweep_results": [
            {
                "min_score": round(c.min_score, 2),
                "ratio": round(c.ratio, 3),
                "floor": round(c.floor, 4),
                **{f"R@{k_}": round(c.recall_at[k_], 4) for k_ in ks},
                "empty_frac": round(c.empty_frac, 4),
                "mean_results": round(c.mean_results, 2),
            }
            for c in cells
        ],
        "recommendation": recommendation,
        "current_default": {
            "min_score": current_ms,
            "ratio": current_ratio,
            **{f"R@{k_}": current.recall_at[k_] if current else None for k_ in ks},
            "empty_frac": current.empty_frac if current else None,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  JSON report saved to: {path}")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────


def _parse_range(s: str) -> list[float]:
    """Parse 'start,stop,step' into a list of floats."""
    parts = [float(x.strip()) for x in s.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Expected start,stop,step — got: {s}")
    start, stop, step = parts
    n = int(round((stop - start) / step)) + 1
    return [round(start + i * step, 10) for i in range(n)]


def _ensure_in_grid(xs: list[float], val: float, tol: float = 1e-9) -> list[float]:
    """Insert *val* into *xs* if no element is within *tol* of it."""
    if any(abs(x - val) < tol for x in xs):
        return xs
    xs2 = sorted(xs + [val])
    return xs2


async def main_async(args: argparse.Namespace) -> None:
    # Embedder
    embedder = None
    if args.vector:
        from hebb.embedding.local import LocalEmbedder
        embedder = LocalEmbedder("all-MiniLM-L6-v2")

    # Reranker
    reranker_top_n = args.rerank_top_n
    reranker = None
    if args.rerank:
        reranker = _get_reranker(args.rerank_model, reranker_top_n)

    # Load data
    units = _load_locomo()
    skw = dict(
        keyword_search_enabled=True,
        vector_search_enabled=args.vector,
        graph_search_enabled=False,
        lexical_boost_enabled=True,
        temporal_boost_enabled=False,
        graph_expansion_enabled=False,
        keyword_blend_enabled=True,
    )

    # Parse sweep ranges
    min_scores = _parse_range(args.min_score_range)
    current_ms = 0.8
    current_ratio = 0.625
    ratios = _parse_range(args.rerank_floor_ratio_range) if args.rerank else [1.0]
    # Ensure the current-production default ratio is always in the grid so
    # the "current default" marker resolves in the sweep table and JSON.
    if args.rerank:
        ratios = _ensure_in_grid(ratios, current_ratio)
    ks = [1, 3, 5, 10]

    config = {
        "dataset": "locomo",
        "reranker": args.rerank_model if args.rerank else "none",
        "top_n": reranker_top_n if args.rerank else 0,
        "top_k": max(ks),
        "vector": args.vector,
        "min_score_range": args.min_score_range,
        "rerank_floor_ratio_range": args.rerank_floor_ratio_range if args.rerank else "N/A",
    }

    # Collect results
    all_records: list[QueryRecord] = []
    t0 = time.time()
    for unit in units:
        store, db = await _build_store(unit, embedder)
        searcher = _make_searcher(store, embedder, skw, reranker)
        try:
            recs = await _collect_query_records(
                searcher, unit, reranker_top_n, max(ks), args.limit,
            )
            all_records.extend(recs)
        finally:
            await db.close()
    elapsed = time.time() - t0

    n_queries = len(all_records)
    if n_queries == 0:
        print("No queries found — check dataset.")
        return

    # Print header
    _print_header(config, n_queries)
    print(f"  retrieval time: {elapsed:.1f}s ({elapsed / n_queries:.2f}s/query)")

    # Score distributions
    dists = _score_distributions(all_records)
    _print_distributions(dists)

    # Baseline (no floor)
    baseline = _compute_baseline(all_records, ks)
    print(f"\n--- Baseline (no floor) ---")
    print(f"  " + "  ".join(f"R@{k_}={baseline[f'R@{k_}']:.3f}" for k_ in ks))

    # Sweep
    if args.composite_floor:
        cells = _sweep_composite(all_records, min_scores, ks)
        _print_sweep(cells, ks, current_ms=current_ms, current_ratio=1.0)
        recommendation = _print_recommendation(cells, ks, current_ms=current_ms, current_ratio=1.0)
        if args.output:
            _save_json(Path(args.output), config, dists, cells, ks, recommendation,
                       current_ms=current_ms, current_ratio=1.0, baseline=baseline)
    else:
        cells = _sweep(all_records, min_scores, ratios, ks)
        _print_sweep(cells, ks, current_ms=current_ms, current_ratio=current_ratio)
        recommendation = _print_recommendation(cells, ks, current_ms=current_ms, current_ratio=current_ratio)
        if args.output:
            _save_json(Path(args.output), config, dists, cells, ks, recommendation,
                       current_ms=current_ms, current_ratio=current_ratio, baseline=baseline)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Offline threshold calibration probe for strict-recall floor",
    )
    ap.add_argument("--rerank", action="store_true",
                    help="Enable cross-encoder reranker")
    ap.add_argument("--rerank-model", default="BAAI/bge-reranker-base",
                    help="Cross-encoder model name")
    ap.add_argument("--rerank-top-n", type=int, default=30,
                    help="Number of top candidates to rerank")
    ap.add_argument("--vector", action="store_true",
                    help="Enable vector search path")
    ap.add_argument("--min-score-range", default="0.5,0.95,0.05",
                    help="min_score sweep range: start,stop,step")
    ap.add_argument("--rerank-floor-ratio-range", default="0.3,1.0,0.05",
                    help="rerank_floor_ratio sweep range: start,stop,step")
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap questions per unit; 0 = no limit")
    ap.add_argument("--composite-floor", action="store_true",
                    help="Filter by composite score only (ignore sigmoid), even with reranker")
    ap.add_argument("--output", default=None,
                    help="JSON output path (e.g. eval/reports/threshold_calibration.json)")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
