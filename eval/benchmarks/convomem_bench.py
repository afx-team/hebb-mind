"""ConvoMem benchmark runner.

Standalone bench (intentionally does not reuse ``BaseBenchmark.setup``
or ``BaseBenchmark.run``) because ConvoMem's metric is substring
containment of evidence messages, not QA accuracy.

Ingestion granularity is **per-message**, not per-turn-pair. ConvoMem's
metric checks whether the verbatim evidence message text appears in any
top-k retrieved memory; turn-pair summaries would concatenate two
messages and pad with role markers, blunting the substring match.
Per-message ingestion is also what MemPalace's
``convomem_bench.py`` does, which keeps the head-to-head fair.

Metric (matches ``docs/analysis/mempalace-benchmark-deep-dive.md §2.3``):
    For each question with evidence E and top-k retrieved memories M,
        found = |{e ∈ E : ∃ m ∈ M, e.lower() ⊆ m.lower() or m.lower() ⊆ e.lower()}|
        recall = found / |E|
    A question is "correct" iff ``recall == 1.0``. Per-category mean
    recall is the headline number.
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
    """Create the partition; swallow already-exists errors."""
    try:
        await client.create_partition(partition_id, name=partition_id)
    except Exception:
        pass


class ConvoMemBenchmark(BaseBenchmark):
    """ConvoMem runner — per-message ingest, substring-match recall."""

    benchmark_name = "convomem"
    dataset_name = "ConvoMem"
    # v1: generic ingest + QA accuracy (wrong metric for this dataset).
    # v2: per-message verbatim ingest, substring evidence recall.
    eval_version = "v2"

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        """Ingest one memory per conversation message into a per-scenario partition.

        Each item gets its own partition (keyed by ``scenario_id``) so
        retrieval restricts to that item's conversation only —
        matching MemPalace's fresh-palace-per-item protocol. Speaker is
        recorded for debugging; the substring match itself is
        role-agnostic.
        """
        total = 0
        for scenario in scenarios:
            await _ensure_partition(client, scenario.scenario_id)

            batch: list[dict] = []
            for turn in scenario.conversations:
                text = (turn.content or "").strip()
                if not text:
                    continue
                metadata: dict = {
                    "msg_idx": turn.turn_index,
                    "speaker": turn.role,
                }
                batch.append({
                    "content": text[:10000],
                    "partition_id": scenario.scenario_id,
                    "importance_score": 5.0,
                    "tags": ["convomem-msg"],
                    "metadata": metadata,
                    "source": "convomem",
                })

                if len(batch) >= self.settings.batch_size:
                    await client.create_memories_batch(batch)
                    total += len(batch)
                    batch.clear()

            if batch:
                await client.create_memories_batch(batch)
                total += len(batch)

        logger.info(
            "Ingested %d ConvoMem messages across %d per-scenario partitions",
            total, len(scenarios),
        )

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        """Retrieve top-k and score by substring evidence recall."""
        sem = asyncio.Semaphore(self.settings.concurrency)
        top_k = self.settings.search_top_k

        async def evaluate(q: EvalQuestion) -> RetrievalResult:
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
                related_list: list[dict] = (
                    raw.get("related", []) if isinstance(raw, dict) else []
                )
                latency_ms = (time.monotonic() - t0) * 1000

                memory_contents: list[str] = []
                for r in results_list:
                    content = (r.get("memory") or {}).get("content")
                    if content:
                        memory_contents.append(content)
                for r in related_list:
                    content = r.get("content")
                    if content:
                        memory_contents.append(content)

                relevance_scores = [r.get("relevance_score", 0.0) for r in results_list]
                recall = _evidence_substring_recall(q.evidence, memory_contents)

                return RetrievalResult(
                    question_id=q.question_id,
                    question=q.question,
                    ground_truth=q.ground_truth,
                    category=q.category,
                    retrieved_memories=memory_contents,
                    generated_answer="",
                    is_correct=recall >= 1.0,
                    confidence=recall,
                    relevance_scores=relevance_scores,
                    latency_ms=latency_ms,
                )

        tasks = [
            evaluate(q)
            for scenario in scenarios
            for q in scenario.questions
        ]
        logger.info(
            "Evaluating %d ConvoMem questions by substring evidence recall...",
            len(tasks),
        )
        results = await asyncio.gather(*tasks)

        correct = sum(1 for r in results if r.is_correct)
        accuracy = (correct / len(results)) if results else 0.0
        avg_recall = (
            sum(r.confidence for r in results) / len(results) if results else 0.0
        )
        by_category = compute_accuracy_by_category(results)
        avg_latency = (
            sum(r.latency_ms for r in results) / len(results) if results else 0.0
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
            retrieval_metrics={
                "avg_evidence_recall": avg_recall,
                "avg_top1_relevance": (
                    sum(r.relevance_scores[0] for r in results if r.relevance_scores)
                    / len(results) if results else 0.0
                ),
                "perfect_recall_rate": correct / len(results) if results else 0.0,
                "zero_recall_rate": (
                    sum(1 for r in results if r.confidence == 0.0) / len(results)
                    if results else 0.0
                ),
            },
            individual_results=results,
            config={
                "eval_version": self.eval_version,
                "mode": "raw_per_message",
                "metric": "substring_evidence_recall",
                "search_top_k": top_k,
                "concurrency": self.settings.concurrency,
                "weight_recency": self.settings.weight_recency,
                "weight_importance": self.settings.weight_importance,
                "weight_relevance": self.settings.weight_relevance,
                "num_scenarios": len(scenarios),
            },
        )


def _evidence_substring_recall(
    evidence: list[str], memories: list[str]
) -> float:
    """Fraction of evidence texts found (case-insensitive substring) in memories.

    Mirrors MemPalace's bidirectional substring rule from
    ``convomem_bench.py:208`` — credit a match when either the evidence
    is contained in a retrieved memory, OR a retrieved memory is
    contained in the evidence (the latter handles cases where the
    indexed unit is a strict prefix/suffix of the evidence string).
    """
    if not evidence:
        return 1.0
    lowered_mems = [m.strip().lower() for m in memories if m]
    if not lowered_mems:
        return 0.0

    found = 0
    for ev in evidence:
        ev_norm = ev.strip().lower()
        if not ev_norm:
            continue
        for mem in lowered_mems:
            if ev_norm in mem or mem in ev_norm:
                found += 1
                break
    return found / len(evidence)
