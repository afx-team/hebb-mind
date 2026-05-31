"""LongMemEval benchmark runner.

Standalone bench (intentionally does not reuse ``BaseBenchmark.setup`` or
``BaseBenchmark.run``) because LongMemEval's scoring is session-level
Recall@k against ``answer_session_ids`` — there is no LLM judge in the
loop, the metric is identical to what MemPalace's
``longmemeval_bench.py`` reports.

Ingestion mirrors the production Claude Code hook surface (same model
used by LoCoMo): every user utterance becomes one ``user-prompt`` memory
and every user+assistant pair becomes one ``turn-summary`` memory. This
is the "what would the hooks actually write" baseline.

Metric:
    For each question, retrieve top-K memories, collect the set of
    ``session_id`` values carried in their metadata, and score:
        recall_any@k = 1.0 iff any answer_session_id ∈ retrieved
        recall_all@k = 1.0 iff every answer_session_id ∈ retrieved
        ndcg_any@k   = standard binary-relevance NDCG over the ranked
                       session-id sequence (deduplicated by first
                       occurrence rank).
    A question is "correct" iff ``recall_any@k == 1.0`` at the
    configured ``search_top_k`` (default 10).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone

from eval.benchmarks.base import (
    BaseBenchmark,
    BenchmarkResult,
    RetrievalResult,
)
from eval.client import HebbClient
from eval.datasets.base import EvalQuestion, EvalScenario
from eval.judge import LLMJudge
from eval.metrics.accuracy import compute_accuracy_by_category
from eval.metrics.retrieval import ndcg_at_k, recall_at_k
from hebb.retrieval.preference_extractor import (
    extract_preferences,
    synthesize_preference_memory,
)

logger = logging.getLogger(__name__)


async def _ensure_partition(client: HebbClient, partition_id: str) -> None:
    """Create the partition; swallow already-exists errors."""
    try:
        await client.create_partition(partition_id, name=partition_id)
    except Exception:
        pass


# Mirror the production hook's _MIN_CONTENT_LENGTH from
# integrations/claude_code/write.py so the per-utterance filter matches.
_MIN_CONTENT_LEN = 20


class LongMemEvalBenchmark(BaseBenchmark):
    """LongMemEval runner aligned with the production hook surface."""

    benchmark_name = "longmemeval"
    dataset_name = "LongMemEval"
    # v1: BaseBenchmark generic ingest + QA accuracy (wrong metric).
    # v2: prod-hook mirror (per-utterance + per-pair), session-level R@k.
    eval_version = "v2"

    # Forward a symmetric turn-context window to /api/v1/search — same
    # default as LoCoMo bench, picks up neighbouring user utterances that
    # share a session without bloating the candidate pool.
    prev_turns: int = 2
    next_turns: int = 2

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        """Two-pass ingestion mirroring write.py + stop.py exactly.

        Each scenario (=one question's haystack) lands in its own
        partition keyed by ``scenario_id`` so search at evaluation
        time restricts to that question's history — matching
        MemPalace's fresh-palace-per-item protocol. Without this, top-k
        slots get filled by sessions from OTHER questions and R@k
        collapses.
        """
        total = 0
        for scenario in scenarios:
            await _ensure_partition(client, scenario.scenario_id)

            turns = sorted(
                scenario.conversations,
                key=lambda t: t.turn_index if t.turn_index is not None else 0,
            )

            batch: list[dict] = []
            seen_hashes: dict[str | None, set[str]] = {}

            # ----- Pass 1: per-user-utterance memories (write.py) -----
            # LongMemEval interleaves user/assistant turns within a
            # session; the production write hook only fires on user
            # prompts, so we filter by role here.
            for turn in turns:
                if turn.role != "user":
                    continue
                content = (turn.content or "").strip()
                if len(content) < _MIN_CONTENT_LEN:
                    continue

                bucket = seen_hashes.setdefault(turn.session_id, set())
                digest = hashlib.sha256(content.lower().encode()).hexdigest()
                if digest in bucket:
                    continue
                bucket.add(digest)

                metadata: dict = {}
                if turn.session_id is not None:
                    metadata["session_id"] = str(turn.session_id)
                if turn.turn_index is not None:
                    metadata["turn"] = turn.turn_index
                if turn.timestamp is not None:
                    metadata["timestamp"] = turn.timestamp

                batch.append({
                    "content": content[:10000],
                    "partition_id": scenario.scenario_id,
                    "importance_score": 5.0,
                    "tags": ["longmemeval"],
                    "metadata": metadata,
                    "source": "hook",
                })

                # Mirror integrations/claude_code/write.py: emit one
                # short synthetic memory per preference / concern /
                # nostalgia phrase the utterance contains. Lifts
                # query→corpus vocabulary overlap on the
                # single-session-preference and temporal-reasoning
                # categories.
                for phrase in extract_preferences(content):
                    pref_metadata = dict(metadata)
                    pref_metadata["synthetic"] = True
                    batch.append({
                        "content": synthesize_preference_memory(phrase)[:10000],
                        "partition_id": scenario.scenario_id,
                        "importance_score": 4.0,
                        "tags": ["longmemeval"],
                        "metadata": pref_metadata,
                        "source": "hook:preference",
                    })

                if len(batch) >= self.settings.batch_size:
                    await client.create_memories_batch(batch)
                    total += len(batch)
                    batch.clear()

            # ----- Pass 2: per-pair turn-summary memories (stop.py) -----
            # A round-trip is (user_i, assistant_{i+1}). The dataset is
            # well-formed so consecutive turns alternate roles, but we
            # explicitly check rather than assume.
            for i in range(0, len(turns) - 1):
                t1, t2 = turns[i], turns[i + 1]
                if t1.role != "user" or t2.role != "assistant":
                    continue
                left = (t1.content or "").strip()
                right = (t2.content or "").strip()
                if not left and not right:
                    continue

                lines: list[str] = []
                if t1.timestamp:
                    lines.append(f"[{t1.timestamp}]")
                if left:
                    lines.append(f"[{t1.role}] {left}")
                if right:
                    lines.append(f"[{t2.role}] {right}")
                summary = "\n".join(lines)
                if len(summary) < _MIN_CONTENT_LEN:
                    continue

                metadata = {}
                if t1.session_id is not None:
                    metadata["session_id"] = str(t1.session_id)
                if t1.timestamp is not None:
                    metadata["timestamp"] = t1.timestamp
                metadata["turn_pair"] = [t1.turn_index, t2.turn_index]

                batch.append({
                    "content": summary[:10000],
                    "partition_id": scenario.scenario_id,
                    "importance_score": 4.0,
                    "tags": ["longmem"],
                    "metadata": metadata,
                    "source": "hook:stop",
                })

                if len(batch) >= self.settings.batch_size:
                    await client.create_memories_batch(batch)
                    total += len(batch)
                    batch.clear()

            if batch:
                await client.create_memories_batch(batch)
                total += len(batch)

        logger.info(
            "Ingested %d memories across %d per-scenario partitions "
            "(per-user-prompt + per-turn-pair, no chunking, no LLM enrichment)",
            total, len(scenarios),
        )

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        """Retrieve top-k and score each question by session-level R@k.

        ``judge`` is accepted only to satisfy the ``Benchmark`` protocol
        — LongMemEval scoring is purely retrieval-based.
        """
        sem = asyncio.Semaphore(self.settings.concurrency)
        # Score the same set of k values MemPalace reports, so head-to-head
        # tables can lift any subset directly.
        ks = (1, 3, 5, 10)
        top_k = max(max(ks), self.settings.search_top_k)

        async def evaluate(q: EvalQuestion) -> tuple[RetrievalResult, dict[str, float]]:
            answer_sids = [
                str(s) for s in q.metadata.get("answer_session_ids", [])
            ]
            # LongMemEval adapter sets question_id == scenario_id.
            scenario_id = q.question_id
            async with sem:
                t0 = time.monotonic()
                raw = await client.search(
                    query=q.question,
                    partition_ids=[scenario_id],
                    top_k=top_k,
                    weight_recency=self.settings.weight_recency,
                    weight_importance=self.settings.weight_importance,
                    weight_relevance=self.settings.weight_relevance,
                    prev_turns=self.prev_turns,
                    next_turns=self.next_turns,
                )
                results_list = raw.get("results", raw) if isinstance(raw, dict) else raw
                related_list: list[dict] = (
                    raw.get("related", []) if isinstance(raw, dict) else []
                )
                latency_ms = (time.monotonic() - t0) * 1000

                # Build the ranked sequence of session_ids in retrieval
                # order. Deduplicate by first occurrence so NDCG penalises
                # the FIRST rank a relevant session shows up at, not the
                # 12th if the same session also appears later.
                ranked_sessions: list[str] = []
                seen: set[str] = set()
                memory_contents: list[str] = []

                def _absorb(mem_obj: dict) -> None:
                    content = mem_obj.get("content")
                    if content:
                        memory_contents.append(content)
                    sid = (mem_obj.get("metadata") or {}).get("session_id")
                    if sid is None:
                        return
                    sid_str = str(sid)
                    if sid_str in seen:
                        return
                    seen.add(sid_str)
                    ranked_sessions.append(sid_str)

                for r in results_list:
                    _absorb(r.get("memory", {}))
                for r in related_list:
                    _absorb(r)

                relevance_scores = [r.get("relevance_score", 0.0) for r in results_list]

                per_q_metrics: dict[str, float] = {}
                for k in ks:
                    per_q_metrics[f"recall_any@{k}"] = float(
                        bool(set(ranked_sessions[:k]) & set(answer_sids))
                    ) if answer_sids else 0.0
                    per_q_metrics[f"recall_all@{k}"] = (
                        recall_at_k(ranked_sessions, answer_sids, k)
                        if answer_sids else 0.0
                    )
                    per_q_metrics[f"ndcg@{k}"] = (
                        ndcg_at_k(ranked_sessions, answer_sids, k)
                        if answer_sids else 0.0
                    )

                primary = per_q_metrics[f"recall_any@{self.settings.search_top_k}"] \
                    if f"recall_any@{self.settings.search_top_k}" in per_q_metrics \
                    else per_q_metrics["recall_any@10"]

                return (
                    RetrievalResult(
                        question_id=q.question_id,
                        question=q.question,
                        ground_truth=q.ground_truth,
                        category=q.category,
                        retrieved_memories=memory_contents,
                        generated_answer="",
                        is_correct=bool(primary),
                        confidence=per_q_metrics.get("recall_all@10", 0.0),
                        relevance_scores=relevance_scores,
                        latency_ms=latency_ms,
                    ),
                    per_q_metrics,
                )

        tasks = [
            evaluate(q)
            for scenario in scenarios
            for q in scenario.questions
        ]
        logger.info("Evaluating %d questions by session-level R@k...", len(tasks))
        paired: list[tuple[RetrievalResult, dict[str, float]]] = await asyncio.gather(*tasks)
        results = [p[0] for p in paired]
        per_q_metrics_list = [p[1] for p in paired]

        # Scorable = has at least one answer_session_id. Questions
        # without (shouldn't happen on LME-S, but be defensive) are
        # excluded from R@k denominators.
        scorable_idx = [
            i for i, r in enumerate(results)
            if scenario_q_for(scenarios, r.question_id)
            and scenario_q_for(scenarios, r.question_id).metadata.get("answer_session_ids")
        ]

        def _mean(metric: str) -> float:
            vals = [per_q_metrics_list[i][metric] for i in scorable_idx]
            return sum(vals) / len(vals) if vals else 0.0

        retrieval_metrics: dict[str, float] = {}
        for k in ks:
            retrieval_metrics[f"recall_any@{k}"] = _mean(f"recall_any@{k}")
            retrieval_metrics[f"recall_all@{k}"] = _mean(f"recall_all@{k}")
            retrieval_metrics[f"ndcg@{k}"] = _mean(f"ndcg@{k}")
        retrieval_metrics["avg_top1_relevance"] = (
            sum(r.relevance_scores[0] for r in results if r.relevance_scores)
            / len(results) if results else 0.0
        )
        retrieval_metrics["no_evidence_excluded"] = len(results) - len(scorable_idx)

        scorable_results = [results[i] for i in scorable_idx]
        correct = sum(1 for r in scorable_results if r.is_correct)
        accuracy = (correct / len(scorable_results)) if scorable_results else 0.0
        by_category = compute_accuracy_by_category(scorable_results)
        avg_latency = (
            sum(r.latency_ms for r in results) / len(results) if results else 0.0
        )

        return BenchmarkResult(
            benchmark_name=self.benchmark_name,
            dataset_name=self.dataset_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_questions=len(scorable_results),
            correct=correct,
            accuracy=accuracy,
            accuracy_by_category={
                cat: info["accuracy"] for cat, info in by_category.items()
            },
            avg_latency_ms=avg_latency,
            retrieval_metrics=retrieval_metrics,
            individual_results=results,
            config={
                "eval_version": self.eval_version,
                "mode": "raw_production_mirror",
                "metric": "session_level_recall_at_k",
                "search_top_k": self.settings.search_top_k,
                "concurrency": self.settings.concurrency,
                "weight_recency": self.settings.weight_recency,
                "weight_importance": self.settings.weight_importance,
                "weight_relevance": self.settings.weight_relevance,
                "num_scenarios": len(scenarios),
                "no_evidence_excluded": len(results) - len(scorable_results),
            },
        )


class LongMemEvalSessionDocBenchmark(LongMemEvalBenchmark):
    """Session-doc ingest variant — one memory per haystack session.

    Isolates *ingest granularity* as a variable so the gap vs MemPalace's
    published R@5 (96.6% raw / 98.4% hybrid v2 on MiniLM-384) can be
    attributed to embedding model + lexical hybrid rather than the prod
    hook's per-utterance ingest. Inherits ``run()`` unchanged — scoring is
    still session-level R@k against ``answer_session_ids``.

    Trade-offs vs the parent v2 bench:
      * MemoryCreate caps content at 10000 chars; ~50% of LongMemEval
        sessions exceed that. We truncate; bge-large's 512-token (~2000
        char) embedding cap is the real bottleneck anyway, and MemPalace
        on MiniLM-384 hits the same ceiling.
      * ``prev_turns`` / ``next_turns`` set to 0 — each memory IS a whole
        session, so neighbour expansion would just pull in adjacent
        sessions and inflate top-k.
    """

    benchmark_name = "longmemeval-session"
    dataset_name = "LongMemEval (session-doc ingest)"
    eval_version = "v1"

    prev_turns = 0
    next_turns = 0

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        """One verbatim doc per session, partition-isolated per question."""
        total = 0
        for scenario in scenarios:
            await _ensure_partition(client, scenario.scenario_id)

            sessions_by_id: dict[str, list] = {}
            for turn in scenario.conversations:
                if turn.session_id is None:
                    continue
                sessions_by_id.setdefault(str(turn.session_id), []).append(turn)

            batch: list[dict] = []
            for session_id, turns in sessions_by_id.items():
                turns = sorted(
                    turns,
                    key=lambda t: t.turn_index if t.turn_index is not None else 0,
                )

                timestamp = next((t.timestamp for t in turns if t.timestamp), None)

                lines: list[str] = []
                if timestamp:
                    lines.append(f"[{timestamp}]")
                for t in turns:
                    content = (t.content or "").strip()
                    if not content:
                        continue
                    lines.append(f"[{t.role}] {content}")
                doc = "\n".join(lines)
                if len(doc) < _MIN_CONTENT_LEN:
                    continue

                metadata: dict = {"session_id": session_id}
                if timestamp:
                    metadata["timestamp"] = timestamp

                batch.append({
                    "content": doc[:10000],
                    "partition_id": scenario.scenario_id,
                    "importance_score": 5.0,
                    "tags": ["session-doc"],
                    "metadata": metadata,
                    "source": "session-doc",
                })

                if len(batch) >= self.settings.batch_size:
                    await client.create_memories_batch(batch)
                    total += len(batch)
                    batch.clear()

            if batch:
                await client.create_memories_batch(batch)
                total += len(batch)

        logger.info(
            "Ingested %d session-doc memories across %d per-scenario partitions",
            total, len(scenarios),
        )


def scenario_q_for(
    scenarios: list[EvalScenario], question_id: str
) -> EvalQuestion | None:
    """Return the original EvalQuestion for a given question_id.

    Module-level helper so the bench can re-read ``metadata`` after
    ``asyncio.gather`` returns plain ``RetrievalResult`` objects. Kept
    out of the class body to avoid binding ``self`` across the awaited
    boundary.
    """
    for scenario in scenarios:
        for q in scenario.questions:
            if q.question_id == question_id:
                return q
    return None
