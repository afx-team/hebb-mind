"""Fast offline multi-dataset retrieval lab for the TEXT-retrieval path.

Replicates each benchmark's ingest protocol + native retrieval metric in
process (in-memory SQLite FTS5, real `MemorySearcher`, no server, no LLM
judge) so a keyword/lexical retrieval change can be A/B'd across LoCoMo,
LongMemEval, and MemBench in minutes instead of the ~hour the server
harness costs.

Metrics (pure retrieval — match the production bench classes):
  * locomo       — session-level Recall_any@k (single shared partition)
  * longmemeval  — session-level Recall_any@k (per-scenario partition)
  * membench     — turn-level Hit@k vs target_step_id (sid OR global_idx)

Run:
  python -m eval.retrieval_lab --dataset locomo --limit 0
  python -m eval.retrieval_lab --dataset all --vector
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import hebb.storage._sqlite_compat  # noqa: F401  patch sqlite3 -> pysqlite3 for vec0
import aiosqlite

from eval.datasets import ADAPTERS
from eval.datasets.locomo import LoCoMoAdapter
from hebb.models.memory import MemoryCreate, MemoryMetadata, MemoryQuery
from hebb.retrieval.preference_extractor import extract_preferences, synthesize_preference_memory
from hebb.retrieval.searcher import MemorySearcher
from hebb.storage.migrations import get_connection, initialize_schema
from hebb.storage.sqlite_store import SQLiteMemoryStore

logging.disable(logging.WARNING)

_MIN_CONTENT_LEN = 20
_DATA = {
    "locomo": "eval/data/locomo/locomo10.json",
    "longmemeval": "eval/data/longmemeval/longmemeval_s.json",
    "membench": "eval/data/membench/membench_noisy_movie.json",
    "personamem": "eval/data/personamem",
}


class NullEmbedder:
    @property
    def dimension(self) -> int:
        return 384

    async def embed(self, text: str) -> list[float]:
        return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


@dataclass
class Doc:
    content: str
    metadata: dict


@dataclass
class Q:
    qid: str
    text: str
    relevant: set[str]      # gold keys (session ids, or step ids as str)
    category: str = ""


@dataclass
class Unit:
    """One retrieval unit = one isolated partition (its own corpus + questions)."""

    pid: str
    docs: list[Doc] = field(default_factory=list)
    questions: list[Q] = field(default_factory=list)


# ----------------------------------------------------------------------
# Per-dataset ingest protocols (mirror the production bench classes)
# ----------------------------------------------------------------------

def _locomo_units() -> tuple[list[Unit], str, int, int]:
    """LoCoMo: ONE shared partition, per-utterance + per-pair, session R@k."""
    adapter = LoCoMoAdapter()
    scenarios = adapter.load(Path(_DATA["locomo"]))
    unit = Unit(pid="mem_hippocampus")
    for sc in scenarios:
        turns = sorted(sc.conversations, key=lambda t: t.turn_index or 0)
        seen: dict[str | None, set[str]] = {}
        # per-utterance
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
        # questions (session-level evidence)
        for q in sc.questions:
            ev = q.evidence or []
            sessions = set()
            for e in ev:
                if e is None:
                    continue
                import re as _re
                m = _re.match(r"^\s*D\s*(\d+)\s*:\s*\d+\s*$", str(e), _re.IGNORECASE)
                if m:
                    sessions.add(m.group(1))
            if not sessions or not (q.question or "").strip():
                continue
            unit.questions.append(Q(q.question_id, q.question, sessions, q.category))
    return [unit], "session", 2, 2


def _longmemeval_units(limit: int) -> tuple[list[Unit], str, int, int]:
    """LongMemEval: per-scenario partition, per-user-utt + per-pair (+pref)."""
    scenarios = ADAPTERS["longmemeval"]().load(Path(_DATA["longmemeval"]))
    if limit:
        scenarios = scenarios[:limit]
    units: list[Unit] = []
    for sc in scenarios:
        unit = Unit(pid=sc.scenario_id)
        turns = sorted(sc.conversations, key=lambda t: t.turn_index or 0)
        seen: dict[str | None, set[str]] = {}
        for t in turns:
            if t.role != "user":
                continue
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
            for phrase in extract_preferences(c):
                pmd = dict(md)
                pmd["synthetic"] = True
                unit.docs.append(Doc(synthesize_preference_memory(phrase)[:10000], pmd))
        for i in range(0, len(turns) - 1):
            t1, t2 = turns[i], turns[i + 1]
            if t1.role != "user" or t2.role != "assistant":
                continue
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
        for q in sc.questions:
            sids = {str(s) for s in q.metadata.get("answer_session_ids", [])}
            if not sids:
                continue
            unit.questions.append(Q(q.question_id, q.question, sids, q.category))
        if unit.docs and unit.questions:
            units.append(unit)
    return units, "session", 2, 2


def _membench_units(limit: int) -> tuple[list[Unit], str, int, int]:
    """MemBench: per-scenario partition, per-turn, turn-level Hit@k."""
    scenarios = ADAPTERS["membench"]().load(Path(_DATA["membench"]))
    if limit:
        scenarios = scenarios[:limit]
    units: list[Unit] = []
    for sc in scenarios:
        unit = Unit(pid=sc.scenario_id)
        for t in sc.conversations:
            c = (t.content or "").strip()
            if not c:
                continue
            tm = t.metadata or {}
            md = {
                "sid": int(tm.get("sid", t.turn_index)),
                "global_idx": int(tm.get("global_idx", t.turn_index)),
            }
            if t.timestamp:
                md["timestamp"] = t.timestamp
            unit.docs.append(Doc(c[:10000], md))
        for q in sc.questions:
            targets = {str(t) for t in q.metadata.get("target_step_ids", [])}
            if not targets:
                continue
            unit.questions.append(Q(q.question_id, q.question, targets, q.category))
        if unit.docs and unit.questions:
            units.append(unit)
    return units, "step", 0, 0


# ----------------------------------------------------------------------
# Store + search
# ----------------------------------------------------------------------

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


def _ranked_keys(resp, metric: str) -> list[str]:
    """Ordered keys for the metric, from results then related (dedup)."""
    keys: list[str] = []
    seen: set[str] = set()

    def _add(md: dict) -> None:
        if metric == "session":
            v = md.get("session_id")
            vals = [str(v)] if v is not None else []
        else:  # step: match sid OR global_idx
            vals = [str(md[k]) for k in ("sid", "global_idx") if k in md]
        for x in vals:
            if x not in seen:
                seen.add(x)
                keys.append(x)

    for r in resp.results:
        _add(r.memory.metadata.model_dump())
    for m in resp.related:
        _add(m.metadata.model_dump())
    return keys


_RERANKER = None


def _get_reranker(model: str, top_n: int):
    global _RERANKER
    if _RERANKER is None:
        from hebb.retrieval.rerank.local import LocalReranker
        _RERANKER = LocalReranker(model_name=model, top_n=top_n)
    return _RERANKER


def _make_searcher(store, embedder, skw, kw_cfg, reranker=None):
    if kw_cfg is None:
        return MemorySearcher(store, embedder or NullEmbedder(), graph=None, reranker=reranker, **skw)
    from eval.kw_experiments import LabSearcher
    return LabSearcher(store, embedder or NullEmbedder(), graph=None, reranker=reranker, kw_cfg=kw_cfg, **skw)


async def run_dataset(name: str, args, embedder, kw_cfg=None, reranker=None) -> dict:
    if name == "locomo":
        units, metric, pv, nx = _locomo_units()
    elif name == "longmemeval":
        units, metric, pv, nx = _longmemeval_units(args.limit)
    elif name == "membench":
        units, metric, pv, nx = _membench_units(args.limit)
    else:
        raise ValueError(name)

    ks = (1, 3, 5, 10, 20, 30, 50) if args.deep else (1, 3, 5, 10)
    hits = {k: 0 for k in ks}
    total = 0
    per_cat: dict[str, list[int]] = {}

    skw = dict(
        keyword_search_enabled=not getattr(args, "no_keyword", False),
        vector_search_enabled=args.vector,
        graph_search_enabled=False,
        lexical_boost_enabled=not args.no_lexical_boost,
        temporal_boost_enabled=False,
        graph_expansion_enabled=False,
        keyword_blend_enabled=not args.no_blend,
    )

    # kw-channel-only: measure the keyword channel in isolation (raw FTS
    # ranking, no fusion / turn-expansion / rerank / IDF-calibration). This is
    # the "kw 本质 / 基础素质" measurement.
    kw_channel = getattr(args, "kw_channel", False)
    chan_cache: dict = {}

    def _keys_from_pairs(pairs):
        keys, seen = [], set()
        for mem, _ in pairs:
            md = mem.metadata.model_dump()
            vals = [str(md["session_id"])] if (metric == "session" and md.get("session_id") is not None) \
                else [str(md[k]) for k in ("sid", "global_idx") if k in md]
            for x in vals:
                if x not in seen:
                    seen.add(x); keys.append(x)
        return keys

    for unit in units:
        store, db = await _build_store(unit, embedder)
        searcher = None if kw_channel else _make_searcher(store, embedder, skw, kw_cfg, reranker)
        try:
            qs = unit.questions[: args.qlimit] if args.qlimit else unit.questions
            for q in qs:
                if kw_channel:
                    from eval.kw_experiments import exp_keyword_search
                    if kw_cfg is not None:
                        kw_cfg.overfetch = max(kw_cfg.overfetch, max(ks), getattr(args, "overfetch", 60))
                    pairs = await exp_keyword_search(
                        store, q.text, max(ks), [unit.pid], kw_cfg, chan_cache)
                    keys = _keys_from_pairs(pairs)
                else:
                    resp = await searcher.search(MemoryQuery(
                        query=q.text, top_k=max(ks), partition_ids=[unit.pid],
                        weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0,
                        prev_turns=pv, next_turns=nx,
                    ))
                    keys = _ranked_keys(resp, metric)
                total += 1
                pc = per_cat.setdefault(q.category, [0, 0])
                pc[1] += 1
                got10 = bool(set(keys[:10]) & q.relevant)
                pc[0] += int(got10)
                for k in ks:
                    if set(keys[:k]) & q.relevant:
                        hits[k] += 1
        finally:
            await db.close()

    res = {f"R@{k}" if metric == "session" else f"Hit@{k}": (hits[k] / total if total else 0.0) for k in ks}
    res["_total"] = total
    res["_units"] = len(units)
    res["_per_cat"] = {c: v[0] / v[1] for c, v in sorted(per_cat.items())}
    return res


def _kw_cfg_from_args(args):
    if not args.exp and not getattr(args, "kw_channel", False):
        return None
    from eval.kw_experiments import KwConfig
    return KwConfig(
        synonyms=not args.no_synonyms,
        phrase=args.phrase,
        scorer=args.scorer,
        k1=args.k1, b=args.b, delta=args.delta,
        rm3=args.rm3, rm3_terms=args.rm3_terms, rm3_topdocs=args.rm3_topdocs,
        overfetch=getattr(args, "overfetch", 60),
        blend_cov=getattr(args, "blend_cov", 0.6),
        blend_prox=getattr(args, "blend_prox", 0.4),
    )


def _sweep_configs():
    """Named keyword configs to compare. Edit freely while iterating."""
    from eval.kw_experiments import KwConfig
    return [
        ("baseline(syn)", KwConfig(synonyms=True)),
        ("nosyn", KwConfig(synonyms=False)),
        ("phrase", KwConfig(synonyms=True, phrase=True)),
        ("phrase+nosyn", KwConfig(synonyms=False, phrase=True)),
        ("rm3", KwConfig(synonyms=True, rm3=True)),
        ("phrase+nosyn+rm3", KwConfig(synonyms=False, phrase=True, rm3=True)),
    ]


# ---------------------------------------------------------------------------
# Floor probe — measure how recall_min_score + rerank_floor_ratio affect
# retrieval quality and query emptiness on labelled data.
# ---------------------------------------------------------------------------

_FLOOR_SWEEP_POINTS: list[tuple[float, float, str]] = [
    # (min_score, rerank_floor_ratio, label)
    # Sweep min_score from 0.4 to 0.9, ratio from 0.3 to 0.8
    # — covers the full range so we can see where each threshold bites.
    (0.4, 0.500, "ms=0.4_r=0.50"),
    (0.4, 0.625, "ms=0.4_r=0.625"),
    (0.5, 0.300, "ms=0.5_r=0.30"),
    (0.5, 0.500, "ms=0.5_r=0.50"),
    (0.5, 0.625, "ms=0.5_r=0.625"),
    (0.5, 0.800, "ms=0.5_r=0.80"),
    (0.6, 0.300, "ms=0.6_r=0.30"),
    (0.6, 0.500, "ms=0.6_r=0.50"),
    (0.6, 0.625, "ms=0.6_r=0.625"),
    (0.6, 0.800, "ms=0.6_r=0.80"),
    (0.7, 0.300, "ms=0.7_r=0.30"),
    (0.7, 0.500, "ms=0.7_r=0.50"),
    (0.7, 0.625, "ms=0.7_r=0.625"),
    (0.7, 0.800, "ms=0.7_r=0.80"),
    (0.8, 0.300, "ms=0.8_r=0.30"),
    (0.8, 0.500, "ms=0.8_r=0.50"),
    (0.8, 0.625, "ms=0.8_r=0.625"),   # shipped default
    (0.8, 0.800, "ms=0.8_r=0.80"),
    (0.9, 0.300, "ms=0.9_r=0.30"),
    (0.9, 0.500, "ms=0.9_r=0.50"),
    (0.9, 0.625, "ms=0.9_r=0.625"),
]


@dataclass
class _FloorResult:
    """Per-floor-config aggregate across all queries in one dataset."""

    label: str
    min_score: float
    rerank_floor_ratio: float
    total_q: int = 0
    # unfiltered recall
    uf_hits: dict[int, int] = field(default_factory=dict)   # k -> hit count
    # strict recall
    st_hits: dict[int, int] = field(default_factory=dict)   # k -> hit count
    # queries where strict returned empty but unfiltered did not
    emptied: int = 0
    # per-category emptied breakdown
    emptied_by_cat: dict[str, int] = field(default_factory=dict)


async def _run_floor_probe_one(
    name: str,
    args,
    embedder,
    reranker,
    min_score: float,
    rerank_floor_ratio: float,
    label: str,
) -> _FloorResult:
    """Run one (min_score, ratio) config against a dataset and return the result."""
    if name == "locomo":
        units, metric, pv, nx = _locomo_units()
    elif name == "longmemeval":
        units, metric, pv, nx = _longmemeval_units(args.limit)
    elif name == "membench":
        units, metric, pv, nx = _membench_units(args.limit)
    else:
        raise ValueError(name)

    ks = (1, 3, 5, 10)
    fr = _FloorResult(label=label, min_score=min_score, rerank_floor_ratio=rerank_floor_ratio)
    fr.uf_hits = {k: 0 for k in ks}
    fr.st_hits = {k: 0 for k in ks}

    skw = dict(
        keyword_search_enabled=not getattr(args, "no_keyword", False),
        vector_search_enabled=args.vector,
        graph_search_enabled=False,
        lexical_boost_enabled=not args.no_lexical_boost,
        temporal_boost_enabled=False,
        graph_expansion_enabled=False,
        keyword_blend_enabled=not args.no_blend,
    )

    for unit in units:
        store, db = await _build_store(unit, embedder)
        searcher = _make_searcher(store, embedder, skw, None, reranker)
        try:
            qs = unit.questions[: args.qlimit] if args.qlimit else unit.questions
            for q in qs:
                fr.total_q += 1
                # --- unfiltered ---
                resp_uf = await searcher.search(MemoryQuery(
                    query=q.text, top_k=max(ks), partition_ids=[unit.pid],
                    weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0,
                    prev_turns=pv, next_turns=nx, min_score=0.0,
                ), rerank_floor_ratio=rerank_floor_ratio)
                keys_uf = _ranked_keys(resp_uf, metric)

                # --- strict ---
                resp_st = await searcher.search(MemoryQuery(
                    query=q.text, top_k=max(ks), partition_ids=[unit.pid],
                    weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0,
                    prev_turns=pv, next_turns=nx, min_score=min_score,
                ), rerank_floor_ratio=rerank_floor_ratio)
                keys_st = _ranked_keys(resp_st, metric)

                # tally hits
                for k in ks:
                    if set(keys_uf[:k]) & q.relevant:
                        fr.uf_hits[k] += 1
                    if set(keys_st[:k]) & q.relevant:
                        fr.st_hits[k] += 1

                # emptied: strict empty but unfiltered non-empty
                if keys_uf and not keys_st:
                    fr.emptied += 1
                    cat = q.category or "unknown"
                    fr.emptied_by_cat[cat] = fr.emptied_by_cat.get(cat, 0) + 1
        finally:
            await db.close()

    return fr


def _print_floor_probe(results: list[_FloorResult], dataset_name: str) -> str:
    """Pretty-print floor probe results and return the report text."""
    ks = sorted(results[0].uf_hits.keys()) if results else [1, 3, 5, 10]
    lines: list[str] = []

    # Header
    col_w = 16
    header = f"{'config':{col_w}s} | {'unfiltered':^{len(ks)*9}s} | {'strict':^{len(ks)*9}s} | {'ΔR@10':>6s} | {'emptied':>7s} | {'empt%':>6s}"
    sub_h = " " * col_w + " | " + " ".join(f"{'R@'+str(k):>8s}" for k in ks) + " | " + " ".join(f"{'R@'+str(k):>8s}" for k in ks) + " |" + " " * 7 + " |" + " " * 8 + " |"

    lines.append(f"\n{'='*90}")
    lines.append(f"  Floor probe: {dataset_name}")
    lines.append(f"{'='*90}")
    lines.append(header)
    lines.append(sub_h)
    lines.append("-" * 90)

    for fr in results:
        uf_str = " ".join(f"{fr.uf_hits[k] / max(fr.total_q, 1):8.3f}" for k in ks)
        st_str = " ".join(f"{fr.st_hits[k] / max(fr.total_q, 1):8.3f}" for k in ks)
        max_k = max(ks)
        delta = (fr.uf_hits[max_k] - fr.st_hits[max_k]) / max(fr.total_q, 1)
        emp_pct = fr.emptied / max(fr.total_q, 1) * 100
        lines.append(f"  {fr.label:{col_w}s} | {uf_str} | {st_str} | {delta:+7.3f} | {fr.emptied:7d} | {emp_pct:5.1f}%")

    # Best pick: lowest emptied% with smallest ΔR@10
    lines.append(f"\n  --- recommendation (lowest emptied% → smallest ΔR@10) ---")
    best = min(results, key=lambda r: (r.emptied / max(r.total_q, 1),
                                        (r.uf_hits[max(ks)] - r.st_hits[max(ks)]) / max(r.total_q, 1)))
    emp_pct = best.emptied / max(best.total_q, 1) * 100
    delta = (best.uf_hits[max(ks)] - best.st_hits[max(ks)]) / max(best.total_q, 1)
    lines.append(f"  best: {best.label}  (min_score={best.min_score}, ratio={best.rerank_floor_ratio})")
    lines.append(f"         emptied={best.emptied}/{best.total_q} ({emp_pct:.1f}%)  ΔR@{max_k}={delta:+.3f}")

    # Per-category breakdown for the shipped default
    shipped = next((r for r in results if r.min_score == 0.8 and r.rerank_floor_ratio == 0.625), None)
    if shipped and shipped.emptied_by_cat:
        lines.append(f"\n  --- per-category emptied (shipped default ms=0.8 r=0.625) ---")
        for cat, cnt in sorted(shipped.emptied_by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"    {cat:28s}: {cnt}")

    report = "\n".join(lines)
    print(report)
    return report


async def _probe_floor(args, embedder, reranker) -> None:
    """Single-config floor probe: compare unfiltered vs strict for one (min_score, ratio)."""
    names = ["locomo", "longmemeval", "membench"] if args.dataset == "all" else [args.dataset]
    ms = getattr(args, "floor_min_score", 0.8)
    rr = getattr(args, "floor_rerank_ratio", 0.625)

    for name in names:
        fr = await _run_floor_probe_one(name, args, embedder, reranker, ms, rr,
                                         f"ms={ms}_r={rr}")
        _print_floor_probe([fr], name)


async def _sweep_floor(args, embedder, reranker) -> None:
    """Sweep multiple (min_score, ratio) combos across datasets.

    Builds each unit's store ONCE, then runs all floor configs against it
    so we don't pay the ingest cost N times.
    """
    names = ["locomo", "longmemeval", "membench"] if args.dataset == "all" else [args.dataset]
    sweep = _FLOOR_SWEEP_POINTS
    start_ts = datetime.now(timezone.utc)
    if getattr(args, "floor_quick", False):
        sweep = [(0.5, 0.500, "ms=0.5_r=0.50"),
                 (0.6, 0.300, "ms=0.6_r=0.30"),
                 (0.6, 0.625, "ms=0.6_r=0.625"),
                 (0.7, 0.500, "ms=0.7_r=0.50"),
                 (0.8, 0.300, "ms=0.8_r=0.30"),
                 (0.8, 0.625, "ms=0.8_r=0.625"),
                 (0.9, 0.500, "ms=0.9_r=0.50")]

    ks = (1, 3, 5, 10)
    skw = dict(
        keyword_search_enabled=not getattr(args, "no_keyword", False),
        vector_search_enabled=args.vector,
        graph_search_enabled=False,
        lexical_boost_enabled=not args.no_lexical_boost,
        temporal_boost_enabled=False,
        graph_expansion_enabled=False,
        keyword_blend_enabled=not args.no_blend,
    )

    for name in names:
        if name == "locomo":
            units, metric, pv, nx = _locomo_units()
        elif name == "longmemeval":
            units, metric, pv, nx = _longmemeval_units(args.limit)
        elif name == "membench":
            units, metric, pv, nx = _membench_units(args.limit)
        else:
            raise ValueError(name)

        # Count total questions for progress reporting
        total_qs = sum(len(unit.questions[: args.qlimit] if args.qlimit else unit.questions) for unit in units)
        print(f"\n{'='*60}")
        print(f"  Dataset: {name}  |  {len(units)} unit(s)  |  {total_qs} questions  |  {len(sweep)} configs")
        print(f"{'='*60}")

        # Init all floor results
        results: list[_FloorResult] = [
            _FloorResult(label=label, min_score=ms, rerank_floor_ratio=rr,
                         uf_hits={k: 0 for k in ks}, st_hits={k: 0 for k in ks})
            for ms, rr, label in sweep
        ]

        q_idx = 0
        for unit in units:
            store, db = await _build_store(unit, embedder)
            searcher = _make_searcher(store, embedder, skw, None, reranker)
            try:
                qs = unit.questions[: args.qlimit] if args.qlimit else unit.questions
                for q in qs:
                    q_idx += 1
                    # Progress: print every 50 questions
                    if q_idx % 50 == 0 or q_idx == 1:
                        print(f"  [{name}] question {q_idx}/{total_qs} ...", flush=True)

                    # unfiltered — same for all configs, do once
                    resp_uf = await searcher.search(MemoryQuery(
                        query=q.text, top_k=max(ks), partition_ids=[unit.pid],
                        weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0,
                        prev_turns=pv, next_turns=nx, min_score=0.0,
                    ))
                    keys_uf = _ranked_keys(resp_uf, metric)

                    for fr in results:
                        fr.total_q += 1
                        # unfiltered hits (same for all configs)
                        for k in ks:
                            if set(keys_uf[:k]) & q.relevant:
                                fr.uf_hits[k] += 1

                        # strict — per-config: real searcher.search() with the
                        # config's min_score + rerank_floor_ratio. The floor is
                        # applied inside searcher.search() on the correct scale
                        # (rerank-sigmoid for the reranked pool, composite for
                        # the tail). This is the validated path — a previous
                        # attempt to reuse the unfiltered rerank result and
                        # floor-filter in Python produced identical scores
                        # across all 21 configs (the floor scale mismatched),
                        # so we pay the 21x search cost deliberately.
                        resp_st = await searcher.search(MemoryQuery(
                            query=q.text, top_k=max(ks), partition_ids=[unit.pid],
                            weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0,
                            prev_turns=pv, next_turns=nx, min_score=fr.min_score,
                        ), rerank_floor_ratio=fr.rerank_floor_ratio)
                        keys_st = _ranked_keys(resp_st, metric)

                        for k in ks:
                            if set(keys_st[:k]) & q.relevant:
                                fr.st_hits[k] += 1

                        if keys_uf and not keys_st:
                            fr.emptied += 1
                            cat = q.category or "unknown"
                            fr.emptied_by_cat[cat] = fr.emptied_by_cat.get(cat, 0) + 1
            finally:
                await db.close()

        report = _print_floor_probe(results, name)

        # Write report file under eval/reports/floor_probe/
        report_dir = Path("eval/reports/floor_probe")
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        report_path = report_dir / f"{name}_{ts}.txt"
        report_path.write_text(report)

        # Also write JSON
        json_path = report_dir / f"{name}_{ts}.json"
        json_data = {
            "dataset": name,
            "total_q": results[0].total_q if results else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "configs": [
                {
                    "label": fr.label,
                    "min_score": fr.min_score,
                    "rerank_floor_ratio": fr.rerank_floor_ratio,
                    "unfiltered": {f"R@{k}": fr.uf_hits[k] / max(fr.total_q, 1) for k in sorted(fr.uf_hits)},
                    "strict": {f"R@{k}": fr.st_hits[k] / max(fr.total_q, 1) for k in sorted(fr.st_hits)},
                    "emptied": fr.emptied,
                    "emptied_pct": fr.emptied / max(fr.total_q, 1) * 100,
                    "emptied_by_cat": fr.emptied_by_cat,
                }
                for fr in results
            ],
        }
        json_path.write_text(json.dumps(json_data, indent=2))
        elapsed = (datetime.now(timezone.utc) - start_ts).total_seconds()
        print(f"\n  [{name}] done in {elapsed:.0f}s  |  Report: {report_path}")
        print(f"  JSON:   {json_path}")


async def main_async(args) -> None:
    embedder = None
    if args.vector:
        from hebb.embedding.local import LocalEmbedder
        embedder = LocalEmbedder("all-MiniLM-L6-v2")

    reranker = _get_reranker(args.rerank_model, args.rerank_top_n) if args.rerank else None

    # Floor probe modes — short-circuit before normal retrieval_lab path
    if args.probe_floor:
        return await _probe_floor(args, embedder, reranker)
    if args.sweep_floor:
        return await _sweep_floor(args, embedder, reranker)

    names = ["locomo", "longmemeval", "membench"] if args.dataset == "all" else [args.dataset]
    if getattr(args, "no_keyword", False):
        base_mode = "vector-only" if args.vector else "EMPTY(no channels)"
    else:
        base_mode = "hybrid" if args.vector else "keyword-only"
    mode = base_mode + ("+rerank" if reranker else "")

    if args.sweep:
        configs = _sweep_configs()
        for name in names:
            print(f"\n========== SWEEP [{name}] ({mode}) ==========")
            header_done = False
            for label, cfg in configs:
                res = await run_dataset(name, args, embedder, cfg, reranker)
                kk = [k for k in res if k.startswith(("R@", "Hit@"))]
                if not header_done:
                    print(f"  units={res['_units']} q={res['_total']}")
                    print(f"  {'config':22s} " + " ".join(f"{k:>8s}" for k in kk))
                    header_done = True
                print(f"  {label:22s} " + " ".join(f"{res[k]:8.3f}" for k in kk))
        return

    kw_cfg = _kw_cfg_from_args(args)
    tag = kw_cfg.tag() if kw_cfg else "baseline"
    print(f"\n========== retrieval_lab ({mode}, cfg={tag}) ==========")
    for name in names:
        res = await run_dataset(name, args, embedder, kw_cfg, reranker)
        kk = [k for k in res if k.startswith(("R@", "Hit@"))]
        line = "  ".join(f"{k}={res[k]:.3f}" for k in kk)
        print(f"\n[{name}]  units={res['_units']} q={res['_total']}")
        print(f"  {line}")
        if args.by_cat:
            for c, v in res["_per_cat"].items():
                print(f"    {c:28s}: {v:.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="all",
                    choices=["all", "locomo", "longmemeval", "membench"])
    ap.add_argument("--vector", action="store_true", help="enable hybrid (vector path)")
    ap.add_argument("--no-lexical-boost", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap scenarios (lme/membench)")
    ap.add_argument("--qlimit", type=int, default=0, help="cap questions per unit (locomo speed)")
    ap.add_argument("--by-cat", action="store_true")
    ap.add_argument("--deep", action="store_true", help="report recall@{1,3,5,10,20,30,50} (ceiling probe)")
    ap.add_argument("--kw-channel", action="store_true", help="measure keyword channel in isolation (no fusion/turn-exp/rerank)")
    ap.add_argument("--no-blend", action="store_true", help="disable keyword blend re-rank in the real searcher")
    ap.add_argument("--no-keyword", action="store_true", help="disable keyword channel (vector-only; use with --vector)")
    ap.add_argument("--overfetch", type=int, default=60, help="keyword candidate pool depth")
    # experimental keyword config
    ap.add_argument("--sweep", action="store_true", help="run the named config sweep table")
    ap.add_argument("--exp", action="store_true", help="use experimental keyword path")
    ap.add_argument("--scorer", default="fts", choices=["fts", "bm25plus", "blend"])
    ap.add_argument("--blend-cov", type=float, default=0.6)
    ap.add_argument("--blend-prox", type=float, default=0.4)
    ap.add_argument("--no-synonyms", action="store_true")
    ap.add_argument("--phrase", action="store_true")
    ap.add_argument("--k1", type=float, default=0.9)
    ap.add_argument("--b", type=float, default=0.4)
    ap.add_argument("--delta", type=float, default=1.0)
    ap.add_argument("--rm3", action="store_true")
    ap.add_argument("--rm3-terms", type=int, default=10)
    ap.add_argument("--rm3-topdocs", type=int, default=5)
    ap.add_argument("--rerank", action="store_true", help="cross-encoder rerank top-N")
    ap.add_argument("--rerank-model", default="BAAI/bge-reranker-base")
    ap.add_argument("--rerank-top-n", type=int, default=30)
    # floor probe — measure impact of recall_min_score + rerank_floor_ratio
    ap.add_argument("--probe-floor", action="store_true",
                    help="Compare unfiltered vs strict-floor recall@k + emptiness rate")
    ap.add_argument("--sweep-floor", action="store_true",
                    help="Sweep multiple (min_score, ratio) combos and recommend best defaults")
    ap.add_argument("--floor-min-score", type=float, default=0.8,
                    help="min_score for --probe-floor (default: 0.8)")
    ap.add_argument("--floor-rerank-ratio", type=float, default=0.625,
                    help="rerank_floor_ratio for --probe-floor (default: 0.625)")
    ap.add_argument("--floor-quick", action="store_true",
                    help="With --sweep-floor: only test 4 key points around the default")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
