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
import logging
from dataclasses import dataclass, field
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
    empty_count = 0
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
                    mq_kwargs: dict[str, object] = dict(
                        query=q.text, top_k=max(ks), partition_ids=[unit.pid],
                        weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0,
                        prev_turns=pv, next_turns=nx,
                    )
                    if args.min_score > 0:
                        mq_kwargs["min_score"] = args.min_score
                        if args.rerank_floor_ratio is not None:
                            mq_kwargs["rerank_floor_ratio"] = args.rerank_floor_ratio
                    resp = await searcher.search(MemoryQuery(**mq_kwargs))
                    keys = _ranked_keys(resp, metric)
                total += 1
                if not keys:
                    empty_count += 1
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
    res["_empty_frac"] = empty_count / total if total else 0.0
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


async def main_async(args) -> None:
    embedder = None
    if args.vector:
        from hebb.embedding.local import LocalEmbedder
        embedder = LocalEmbedder("all-MiniLM-L6-v2")

    reranker = _get_reranker(args.rerank_model, args.rerank_top_n) if args.rerank else None

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
                    print(f"  units={res['_units']} q={res['_total']} empty_frac={res['_empty_frac']:.3f}")
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
        print(f"\n[{name}]  units={res['_units']} q={res['_total']} empty_frac={res['_empty_frac']:.3f}")
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
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="Apply min_score floor (default 0 = no filter)")
    ap.add_argument("--rerank-floor-ratio", type=float, default=None,
                    help="Override rerank floor ratio for strict recall")
    ap.add_argument("--rerank", action="store_true", help="cross-encoder rerank top-N")
    ap.add_argument("--rerank-model", default="BAAI/bge-reranker-base")
    ap.add_argument("--rerank-top-n", type=int, default=30)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
