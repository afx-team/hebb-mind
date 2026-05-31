"""Fast offline keyword-only retrieval probe.

Drives the *real* keyword path (``build_fts_query`` -> FTS5 BM25 ->
``MemorySearcher`` scoring) with vector/graph/rerank disabled, against
LoCoMo (and other) data parsed so each memory carries its gold dia_id.

Two things it measures:
  1. Retrieval quality of the keyword path alone (exact-evidence
     Recall@k at the utterance level, plus session-level R@k to compare
     with the benchmark headline).
  2. Score calibration: for every *scored* result we know whether it is
     a true evidence utterance, so we can ask "is 0.8 a sane boundary?"
     — i.e. do truly-relevant memories land >= 0.8 and irrelevant ones
     below it, comparing the actual content against the query.

Run: python -m eval.kw_probe [--no-lexical-boost] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import hebb.storage._sqlite_compat  # noqa: F401  patch sqlite3 -> pysqlite3 for vec0
import aiosqlite

from hebb.models.memory import MemoryCreate, MemoryMetadata, MemoryQuery
from hebb.retrieval.fts_query import build_fts_query
from hebb.retrieval.lexical_relevance import (
    build_lexical_query,
    cjk_surface_tokens,
    lexical_relevance,
    make_idf,
    query_surface_tokens,
)
from hebb.retrieval.searcher import MemorySearcher
from hebb.storage.migrations import initialize_schema
from hebb.storage.sqlite_store import SQLiteMemoryStore

PARTITION_ID = "mem_hippocampus"
_DIA_RE = re.compile(r"^\s*D\s*(\d+)\s*:\s*(\d+)\s*$", re.IGNORECASE)
_MIN_CONTENT_LEN = 20


class NullEmbedder:
    """Embedder that returns nothing so the vector path is a no-op."""

    @property
    def dimension(self) -> int:
        return 384

    async def embed(self, text: str) -> list[float]:
        return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


@dataclass
class Question:
    qid: str
    text: str
    answer: str
    category: int
    evidence_dia: set[str]          # {"D1:3", ...}  (locomo)
    evidence_sessions: set[str]     # {"1", ...}     (locomo)
    answer_norm: str = ""           # normalized answer for containment labels


@dataclass
class Scenario:
    sid: str
    # memory payloads: (content, dia_id, session_id)
    utterances: list[tuple[str, str, str]] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)


def load_locomo(path: Path) -> list[Scenario]:
    raw = json.loads(path.read_text())
    items = list(raw.values()) if isinstance(raw, dict) else raw
    out: list[Scenario] = []
    for idx, item in enumerate(items):
        sc = Scenario(sid=f"locomo_{idx}")
        conv = item.get("conversation", {})
        session_keys = sorted(
            [k for k in conv if k.startswith("session_") and not k.endswith("_date_time")],
            key=lambda k: int(k.split("_")[1]),
        )
        for sk in session_keys:
            session_id = sk.split("_")[1]
            for t in conv.get(sk, []):
                text = (t.get("text") or "").strip()
                dia = t.get("dia_id", "")
                if not text or not dia:
                    continue
                sc.utterances.append((text, dia, session_id))
        for qi, q in enumerate(item.get("qa", [])):
            ev = q.get("evidence", [])
            if isinstance(ev, str):
                ev = [ev]
            dia = {str(e).strip() for e in ev if e}
            sessions = set()
            for e in dia:
                m = _DIA_RE.match(e)
                if m:
                    sessions.add(m.group(1))
            sc.questions.append(
                Question(
                    qid=f"{sc.sid}_q{qi}",
                    text=q.get("question", ""),
                    answer=str(q.get("answer", "")),
                    category=q.get("category", 0),
                    evidence_dia=dia,
                    evidence_sessions=sessions,
                )
            )
        out.append(sc)
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def load_generic(name: str) -> list[Scenario]:
    """Load any adapter-backed dataset into Scenarios using answer-containment
    labels (dataset-agnostic): a memory is 'relevant' iff it contains the
    ground-truth answer string. Each conversation turn becomes one memory."""
    from eval.datasets import ADAPTERS

    paths = {
        "convomem": "eval/data/convomem/convomem.json",
        "longmemeval": "eval/data/longmemeval/longmemeval_s.json",
        "personamem": "eval/data/personamem",
    }
    adapter = ADAPTERS[name]()
    scenarios_raw = adapter.load(Path(paths[name]))
    out: list[Scenario] = []
    for si, sc in enumerate(scenarios_raw):
        scen = Scenario(sid=f"{name}_{si}")
        for ti, turn in enumerate(sc.conversations):
            text = (turn.content or "").strip()
            if not text:
                continue
            sid = turn.session_id if turn.session_id is not None else "0"
            scen.utterances.append((text, f"{si}:{ti}", str(sid)))
        for qi, q in enumerate(sc.questions):
            ans = _norm(q.ground_truth)
            # Skip degenerate answers (too short / multiple-choice letters).
            if len(ans) < 3:
                continue
            scen.questions.append(
                Question(
                    qid=f"{scen.sid}_q{qi}",
                    text=q.question,
                    answer=q.ground_truth,
                    category=0,
                    evidence_dia=set(),
                    evidence_sessions=set(),
                    answer_norm=ans,
                )
            )
        if scen.utterances and scen.questions:
            out.append(scen)
    return out


async def build_store(
    scenario: Scenario, embedder=None
) -> tuple[SQLiteMemoryStore, aiosqlite.Connection]:
    from hebb.storage.migrations import get_connection

    use_vec = embedder is not None
    db = await get_connection(":memory:", load_vec=use_vec)
    await initialize_schema(db, embedding_dim=(embedder.dimension if use_vec else 384),
                            create_vec_table=use_vec)
    store = SQLiteMemoryStore(db)
    payloads = [
        (content, dia, session_id)
        for content, dia, session_id in scenario.utterances
        if len(content) >= _MIN_CONTENT_LEN
    ]
    embeddings = None
    if use_vec:
        embeddings = await embedder.embed_batch([p[0][:10000] for p in payloads])
    for i, (content, dia, session_id) in enumerate(payloads):
        await store.create(
            MemoryCreate(
                content=content[:10000],
                partition_id=PARTITION_ID,
                importance_score=5.0,
                tags=["locomo"],
                metadata=MemoryMetadata(session_id=session_id, dia_id=dia),
                source="probe",
            ),
            embedding=embeddings[i] if embeddings else None,
        )
    return store, db


@dataclass
class CalibPoint:
    score: float
    relevant: bool   # session-level relevance (retrieved session in evidence)
    exact: bool      # dia-level relevance (this exact utterance is evidence)


async def _total_docs(store: SQLiteMemoryStore) -> int:
    cur = await store.db.execute("SELECT count(*) FROM memory_fts")
    row = await cur.fetchone()
    return int(row[0]) if row else 0


async def _doc_freqs(store: SQLiteMemoryStore, tokens: list[str]) -> dict[str, int]:
    """Document frequency of each surface token via the FTS index itself
    (so FTS porter-stemming on the token matches how the corpus was indexed)."""
    freqs: dict[str, int] = {}
    for tok in tokens:
        try:
            cur = await store.db.execute(
                "SELECT count(*) FROM memory_fts WHERE memory_fts MATCH ?",
                (f'"{tok}"',),
            )
            row = await cur.fetchone()
            freqs[tok] = int(row[0]) if row else 0
        except Exception:
            freqs[tok] = 0
    return freqs


def _l2sim_to_cosine(sim: float) -> float:
    """Recover cosine from the store's 1/(1+L2) similarity (normalized vecs).

    L2 = 1/sim - 1 ; cos = 1 - L2^2/2 for unit vectors. Clamped to [0,1].
    """
    if sim <= 0:
        return 0.0
    l2 = (1.0 / sim) - 1.0
    cos = 1.0 - (l2 * l2) / 2.0
    return max(0.0, min(1.0, cos))


async def _hybrid_cal_search(
    store: SQLiteMemoryStore,
    searcher: MemorySearcher,
    query: str,
    top_k: int,
    total_docs: int,
    *,
    embedder,
    rank_mode: str,
    overfetch: int = 60,
) -> list[tuple[object, float]]:
    """Simulate the proposed scoring: calibrated relevance = max(lexrel, cosine).

    rank_mode='cal' ranks by the calibrated score; rank_mode='rrf' keeps the
    searcher's RRF order and only attaches the calibrated score.
    """
    kw = await store.search_by_keyword(query, top_k=overfetch, partition_ids=[PARTITION_ID])
    emb = await embedder.embed(query)
    vec = await store.search_by_vector(emb, top_k=overfetch, partition_ids=[PARTITION_ID]) if emb else []
    cos: dict[str, float] = {}
    pool: dict[str, object] = {}
    for mem, _ in kw:
        pool[mem.id] = mem
    for mem, sim in vec:
        pool[mem.id] = mem
        cos[mem.id] = _l2sim_to_cosine(sim)
    idf = await _build_idf(store, query, total_docs)
    lq = build_lexical_query(query, idf)
    scored = []
    for mid, mem in pool.items():
        lexrel = lexical_relevance(lq, mem.content)
        relevance = max(lexrel, cos.get(mid, 0.0))
        scored.append((mem, relevance))

    if rank_mode == "rrf":
        # Use the real searcher's RRF order, attach calibrated scores.
        resp = await searcher.search(
            MemoryQuery(query=query, top_k=top_k, partition_ids=[PARTITION_ID],
                        weight_recency=0.0, weight_importance=0.0, weight_relevance=1.0)
        )
        score_by_id = {m.id: s for m, s in scored}
        return [(r.memory, score_by_id.get(r.memory.id, 0.0)) for r in resp.results]

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


async def _build_idf(store: SQLiteMemoryStore, query: str, total_docs: int):
    surface = query_surface_tokens(query) + list(cjk_surface_tokens(query))
    freqs = await _doc_freqs(store, surface)
    return make_idf(freqs, total_docs)


async def _lexrel_search(
    store: SQLiteMemoryStore,
    query: str,
    top_k: int,
    total_docs: int,
    *,
    use_idf: bool,
    keep_fts_order: bool = False,
    overfetch: int = 60,
) -> list[tuple[object, float]]:
    """Keyword candidate generation (FTS) + calibrated lexical rescoring.

    keep_fts_order=True keeps the BM25 candidate ordering (recall) and only
    attaches the calibrated lexrel score; otherwise re-sorts by the score.
    """
    candidates = await store.search_by_keyword(query, top_k=overfetch, partition_ids=[PARTITION_ID])
    if not candidates:
        return []
    idf = await _build_idf(store, query, total_docs) if use_idf else None
    lq = build_lexical_query(query, idf)
    scored = [(mem, lexical_relevance(lq, mem.content)) for mem, _ in candidates]
    if not keep_fts_order:
        scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


async def run(args: argparse.Namespace) -> None:
    containment = args.dataset != "locomo"
    if containment:
        scenarios = load_generic(args.dataset)
    else:
        scenarios = load_locomo(Path("eval/data/locomo/locomo10.json"))
    if args.limit:
        scenarios = scenarios[: args.limit]

    embedder = None
    if args.vector:
        from hebb.embedding.local import LocalEmbedder
        embedder = LocalEmbedder("all-MiniLM-L6-v2")

    searcher_kwargs = dict(
        keyword_search_enabled=True,
        vector_search_enabled=args.vector,
        graph_search_enabled=False,
        lexical_boost_enabled=not args.no_lexical_boost,
        temporal_boost_enabled=False,
        graph_expansion_enabled=False,
    )

    top_k = args.top_k
    # session-level (benchmark headline) and exact dia-level recall
    sess_correct = sess_total = 0
    exact_recall_sum = 0.0
    exact_total = 0
    calib: list[CalibPoint] = []
    per_cat: dict[int, list[int]] = {}

    for sc in scenarios:
        store, db = await build_store(sc, embedder=embedder)
        searcher = MemorySearcher(store, embedder or NullEmbedder(), graph=None, reranker=None, **searcher_kwargs)
        total_docs = await _total_docs(store)
        try:
            for q in sc.questions:
                if not containment and not q.evidence_sessions:
                    continue  # adversarial / no evidence — excluded
                if containment and not q.answer_norm:
                    continue
                if not q.text.strip():
                    continue
                # (memory, score) pairs from the selected scorer
                scored_pairs: list[tuple[object, float]]
                if args.scorer == "rrf":
                    resp = await searcher.search(
                        MemoryQuery(
                            query=q.text,
                            top_k=top_k,
                            partition_ids=[PARTITION_ID],
                            weight_recency=0.0,
                            weight_importance=0.0,
                            weight_relevance=1.0,
                        )
                    )
                    scored_pairs = [(r.memory, r.score) for r in resp.results]
                elif args.scorer in ("hybrid_cal", "hybrid_cal_rrf"):
                    scored_pairs = await _hybrid_cal_search(
                        store, searcher, q.text, top_k, total_docs,
                        embedder=embedder,
                        rank_mode=("rrf" if args.scorer == "hybrid_cal_rrf" else "cal"),
                    )
                elif args.scorer == "bm25_lexrel":
                    # BM25 candidate ordering (recall), calibrated lexrel score
                    scored_pairs = await _lexrel_search(
                        store, q.text, top_k, total_docs,
                        use_idf=True, keep_fts_order=True,
                    )
                else:
                    scored_pairs = await _lexrel_search(
                        store, q.text, top_k, total_docs,
                        use_idf=(args.scorer == "lexrel"),
                    )

                retrieved_sessions: set[str] = set()
                retrieved_dia: set[str] = set()
                answer_found = False
                for mem, score in scored_pairs:
                    md = mem.metadata.model_dump()
                    sid = md.get("session_id")
                    dia = md.get("dia_id")
                    if sid is not None:
                        retrieved_sessions.add(str(sid))
                    if dia:
                        retrieved_dia.add(str(dia))
                    if containment:
                        rel = q.answer_norm in _norm(mem.content)
                        answer_found = answer_found or rel
                        calib.append(CalibPoint(score=score, relevant=rel, exact=rel))
                    else:
                        calib.append(
                            CalibPoint(
                                score=score,
                                relevant=(sid is not None and str(sid) in q.evidence_sessions),
                                exact=(dia in q.evidence_dia),
                            )
                        )
                sess_total += 1
                if containment:
                    hit = answer_found
                else:
                    hit = bool(q.evidence_sessions & retrieved_sessions)
                sess_correct += int(hit)
                per_cat.setdefault(q.category, [0, 0])
                per_cat[q.category][1] += 1
                per_cat[q.category][0] += int(hit)
                # exact dia recall (locomo only)
                if q.evidence_dia:
                    exact_total += 1
                    exact_recall_sum += len(q.evidence_dia & retrieved_dia) / len(q.evidence_dia)
        finally:
            await db.close()

    metric = "answer-containment R@" if containment else "session-level R@"
    vec = "hybrid" if args.vector else "keyword-only"
    print(f"\n=== {args.dataset} {vec} probe (scorer={args.scorer}, top_k={top_k}) ===")
    print(f"questions scored: {sess_total}")
    print(f"{metric}{top_k}: {sess_correct/max(sess_total,1):.3f}")
    if exact_total:
        print(f"exact dia-level mean Recall@{top_k}: {exact_recall_sum/exact_total:.3f}")
    cat_names = {1: "single_hop", 2: "multi_hop", 3: "temporal", 4: "open_ended", 5: "adversarial"}
    for c in sorted(per_cat):
        hit, tot = per_cat[c]
        if c:
            print(f"  cat {c} {cat_names.get(c,'?'):12s}: {hit/tot:.3f} ({hit}/{tot})")

    _calibration_report(calib)


def _calibration_report(calib: list[CalibPoint]) -> None:
    if not calib:
        print("no calibration points")
        return
    rel = [c.score for c in calib if c.relevant]
    irr = [c.score for c in calib if not c.relevant]
    ex = [c.score for c in calib if c.exact]

    def stats(xs: list[float]) -> str:
        if not xs:
            return "n=0"
        xs2 = sorted(xs)
        n = len(xs2)
        mean = sum(xs2) / n
        p50 = xs2[n // 2]
        p10 = xs2[max(0, n // 10)]
        p90 = xs2[min(n - 1, 9 * n // 10)]
        return f"n={n} mean={mean:.3f} p10={p10:.3f} p50={p50:.3f} p90={p90:.3f} min={xs2[0]:.3f} max={xs2[-1]:.3f}"

    print("\n--- score calibration (session-level relevance) ---")
    print(f"relevant   {stats(rel)}")
    print(f"irrelevant {stats(irr)}")
    print(f"exact-evid {stats(ex)}")

    # how does the 0.8 boundary behave?
    for thr in (0.5, 0.6, 0.7, 0.8, 0.9):
        tp = sum(1 for c in calib if c.score >= thr and c.relevant)
        fp = sum(1 for c in calib if c.score >= thr and not c.relevant)
        fn = sum(1 for c in calib if c.score < thr and c.relevant)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        recl = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * recl / (prec + recl) if (prec + recl) else 0.0
        above = tp + fp
        print(f"  thr={thr:.2f}: above={above:4d} precision={prec:.3f} recall={recl:.3f} f1={f1:.3f}")


async def inspect(args: argparse.Namespace) -> None:
    """Print query + scored top-k with evidence flags for eyeballing."""
    scenarios = load_locomo(Path("eval/data/locomo/locomo10.json"))
    sc = scenarios[0]
    store, db = await build_store(sc)
    total_docs = await _total_docs(store)
    try:
        shown = 0
        for q in sc.questions:
            if not q.evidence_dia or not q.text.strip():
                continue
            pairs = await _lexrel_search(
                store, q.text, args.top_k, total_docs, use_idf=True, keep_fts_order=True
            )
            print(f"\nQ: {q.text}")
            print(f"   answer={q.answer!r}  evidence={sorted(q.evidence_dia)}")
            for mem, score in pairs[:6]:
                md = mem.metadata.model_dump()
                dia = md.get("dia_id")
                flag = "✓EVID" if dia in q.evidence_dia else "     "
                txt = mem.content.replace("\n", " ")[:90]
                print(f"   {flag} {score:.3f} [{dia}] {txt}")
            shown += 1
            if shown >= args.limit or shown >= 12:
                break
    finally:
        await db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="locomo",
                    choices=["locomo", "convomem", "longmemeval", "personamem"])
    ap.add_argument("--no-lexical-boost", action="store_true")
    ap.add_argument("--scorer", default="rrf",
                    choices=["rrf", "lexrel", "coverage", "bm25_lexrel", "hybrid_cal", "hybrid_cal_rrf"],
                    help="rrf=current searcher; lexrel=IDF coverage(resorted); coverage=plain; "
                         "bm25_lexrel=BM25 order+lexrel score; hybrid_cal=max(lexrel,cos) ranked; "
                         "hybrid_cal_rrf=RRF order + max(lexrel,cos) score")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--vector", action="store_true", help="Enable vector path (full hybrid via real searcher)")
    ap.add_argument("--inspect", action="store_true", help="Print query+results for eyeballing")
    args = ap.parse_args()
    if args.inspect:
        args.limit = args.limit or 12
        asyncio.run(inspect(args))
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
