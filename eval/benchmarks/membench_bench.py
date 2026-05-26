"""MemBench benchmark runner (ACL 2025).

Standalone bench (intentionally does not reuse ``BaseBenchmark.setup``
or ``BaseBenchmark.run``) because MemBench's metric is turn-level
Hit@k against ``target_step_id``, not QA accuracy or substring
containment.

Ingestion is **one memory per turn pair**, formatted exactly as the
adapter prepared the content (``[User] X [Assistant] Y``). The local
turn id (``sid``) and the cross-session position (``global_idx``) both
land on the memory metadata so Hit@k can match either — MemPalace's
``membench_bench.py:384`` does the same dual-key match because the
dataset is inconsistent about which integer ``target_step_id`` points
at.

Metric:
    Hit@k = 1.0 iff
        (target_step_ids ∩ {m.metadata['sid']      for m in top_k}) ∪
        (target_step_ids ∩ {m.metadata['global_idx'] for m in top_k})
        is non-empty.
    Per-category mean Hit@k is the headline; we report Hit@1, Hit@3,
    Hit@5, Hit@10 so we can table against MemPalace's reported top-5.
"""

from __future__ import annotations

import asyncio
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

logger = logging.getLogger(__name__)


async def _ensure_partition(client: HebbClient, partition_id: str) -> None:
    """Create the partition (idempotent — swallow already-exists errors).

    Each scenario lands in its own partition so search can restrict to
    a single item's haystack. The CLI wipes ``hebb.db`` between runs,
    so a clean run never sees a pre-existing partition; the try/except
    is here so a retry inside one run doesn't crash.
    """
    try:
        await client.create_partition(partition_id, name=partition_id)
    except Exception:
        pass


class MemBenchBenchmark(BaseBenchmark):
    """MemBench runner — per-turn-pair ingest, turn-level Hit@k."""

    benchmark_name = "membench"
    dataset_name = "MemBench"
    # v1: per-turn-pair ingest, dual-key (sid + global_idx) Hit@k.
    eval_version = "v1"

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        """Ingest one memory per turn pair into a per-scenario partition.

        Each scenario gets its own partition keyed by ``scenario_id`` so
        retrieval at search time can restrict to a single item's
        haystack — matching MemPalace's "fresh palace per item"
        protocol. Without this, top-k slots get filled by competing
        scenarios and Hit@k collapses.
        """
        total = 0
        for scenario in scenarios:
            await _ensure_partition(client, scenario.scenario_id)

            batch: list[dict] = []
            for turn in scenario.conversations:
                content = (turn.content or "").strip()
                if not content:
                    continue

                turn_meta = turn.metadata or {}
                metadata: dict = {
                    "sid": int(turn_meta.get("sid", turn.turn_index)),
                    "global_idx": int(turn_meta.get("global_idx", turn.turn_index)),
                    "s_idx": int(turn_meta.get("s_idx", 0)),
                }
                if turn.timestamp:
                    metadata["timestamp"] = turn.timestamp

                batch.append({
                    "content": content[:10000],
                    "partition_id": scenario.scenario_id,
                    "importance_score": 5.0,
                    "tags": ["membench-turn"],
                    "metadata": metadata,
                    "source": "membench",
                })

                if len(batch) >= self.settings.batch_size:
                    await client.create_memories_batch(batch)
                    total += len(batch)
                    batch.clear()

            if batch:
                await client.create_memories_batch(batch)
                total += len(batch)

        logger.info(
            "Ingested %d MemBench turn-pair memories across %d per-scenario partitions",
            total, len(scenarios),
        )

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        """Retrieve top-k and score by turn-level Hit@k."""
        sem = asyncio.Semaphore(self.settings.concurrency)
        ks = (1, 3, 5, 10)
        top_k = max(max(ks), self.settings.search_top_k)

        async def evaluate(q: EvalQuestion) -> tuple[RetrievalResult, dict[str, float]]:
            targets = {int(t) for t in q.metadata.get("target_step_ids", [])}
            scenario_id = q.question_id.rsplit("_q", 1)[0]
            async with sem:
                t0 = time.monotonic()
                raw = await client.search(
                    query=q.question,
                    partition_ids=[scenario_id],
                    top_k=top_k,
                    weight_recency=self.settings.weight_recency,
                    weight_importance=self.settings.weight_importance,
                    weight_relevance=self.settings.weight_relevance,
                )
                results_list = raw.get("results", raw) if isinstance(raw, dict) else raw
                latency_ms = (time.monotonic() - t0) * 1000

                ranked_sids: list[int] = []
                ranked_globals: list[int] = []
                memory_contents: list[str] = []
                for r in results_list:
                    mem = r.get("memory", {})
                    meta = mem.get("metadata") or {}
                    content = mem.get("content")
                    if content:
                        memory_contents.append(content)
                    if "sid" in meta:
                        try:
                            ranked_sids.append(int(meta["sid"]))
                        except (TypeError, ValueError):
                            pass
                    if "global_idx" in meta:
                        try:
                            ranked_globals.append(int(meta["global_idx"]))
                        except (TypeError, ValueError):
                            pass

                relevance_scores = [r.get("relevance_score", 0.0) for r in results_list]

                per_q: dict[str, float] = {}
                for k in ks:
                    hit = bool(
                        (targets & set(ranked_sids[:k]))
                        or (targets & set(ranked_globals[:k]))
                    )
                    per_q[f"hit@{k}"] = float(hit)

                primary_k = self.settings.search_top_k
                primary = per_q.get(f"hit@{primary_k}", per_q["hit@5"])

                return (
                    RetrievalResult(
                        question_id=q.question_id,
                        question=q.question,
                        ground_truth=q.ground_truth,
                        category=q.category,
                        retrieved_memories=memory_contents,
                        generated_answer="",
                        is_correct=bool(primary),
                        confidence=primary,
                        relevance_scores=relevance_scores,
                        latency_ms=latency_ms,
                    ),
                    per_q,
                )

        tasks = [
            evaluate(q)
            for scenario in scenarios
            for q in scenario.questions
        ]
        logger.info(
            "Evaluating %d MemBench questions by turn-level Hit@k...", len(tasks)
        )
        paired = await asyncio.gather(*tasks)
        results = [p[0] for p in paired]
        per_q_metrics_list = [p[1] for p in paired]

        def _mean(metric: str) -> float:
            vals = [m[metric] for m in per_q_metrics_list]
            return sum(vals) / len(vals) if vals else 0.0

        correct = sum(1 for r in results if r.is_correct)
        accuracy = (correct / len(results)) if results else 0.0
        by_category = compute_accuracy_by_category(results)
        avg_latency = (
            sum(r.latency_ms for r in results) / len(results) if results else 0.0
        )

        retrieval_metrics: dict[str, float] = {f"hit@{k}": _mean(f"hit@{k}") for k in ks}
        retrieval_metrics["avg_top1_relevance"] = (
            sum(r.relevance_scores[0] for r in results if r.relevance_scores)
            / len(results) if results else 0.0
        )

        return BenchmarkResult(
            benchmark_name=self.benchmark_name,
            dataset_name=self.dataset_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_questions=len(results),
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
                "mode": "raw_per_turn_pair",
                "metric": "turn_level_hit_at_k",
                "search_top_k": self.settings.search_top_k,
                "concurrency": self.settings.concurrency,
                "weight_recency": self.settings.weight_recency,
                "weight_importance": self.settings.weight_importance,
                "weight_relevance": self.settings.weight_relevance,
                "num_scenarios": len(scenarios),
            },
        )
