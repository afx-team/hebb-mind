"""LoCoMo end-to-end QA benchmark runner.

Inherits the production-hook-mirror ingestion from
:class:`LoComoBenchmark` (per-utterance + per-turn-pair memories, no
chunking, no image captions) and replaces the session-level R@k scorer
with an LLM-as-judge end-to-end QA pipeline:

1. Retrieve top-k for the question via the live ``/api/v1/search``
   endpoint (same hybrid pipeline shipped to production).
2. Ask the judge LLM to ``generate_answer`` from the retrieved memory
   contents.
3. Ask the same judge to ``judge_correctness`` against the ground truth
   using semantic-equivalence rules.

Reports the QA accuracy as the headline and surfaces session-level R@k
in ``retrieval_metrics`` for cross-checking against
:mod:`eval.benchmarks.locomo_bench`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from eval.benchmarks.base import BenchmarkResult, RetrievalResult
from eval.benchmarks.locomo_bench import (
    LoComoBenchmark,
    _evidence_recall,
    _evidence_to_sessions,
)
from eval.client import HebbClient
from eval.datasets.base import EvalQuestion, EvalScenario
from eval.judge import LLMJudge
from eval.metrics.accuracy import compute_accuracy_by_category

logger = logging.getLogger(__name__)


class LoComoQABenchmark(LoComoBenchmark):
    """LoCoMo runner that scores end-to-end QA accuracy under the v3
    production-mirror retrieval pipeline."""

    benchmark_name = "locomo-qa"
    dataset_name = "LoCoMo (end-to-end QA)"
    # v1: QA accuracy on top of v3 retrieval (per-utterance + per-pair
    # ingest, prev/next-turn window, date-proximity boost, FTS5 porter +
    # synonym groups). Replaces the v0.1.1 chunking + image-captions QA
    # runs that lived under ``locomo/v1/run-*``.
    eval_version = "v1"

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        """Retrieve, generate, and judge each question."""
        sem = asyncio.Semaphore(self.settings.concurrency)

        async def _search_with_retry(q: EvalQuestion) -> dict:
            """Retry search on transient ReadTimeouts so one slow encoder
            call doesn't blow up the whole gather.
            """
            last_exc: Exception | None = None
            for attempt in range(3):
                try:
                    return await client.search(
                        query=q.question,
                        top_k=self.settings.search_top_k,
                        weight_recency=self.settings.weight_recency,
                        weight_importance=self.settings.weight_importance,
                        weight_relevance=self.settings.weight_relevance,
                        prev_turns=self.prev_turns,
                        next_turns=self.next_turns,
                    )
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "search() failed for %s on attempt %d/3: %s",
                        q.question_id, attempt + 1, exc,
                    )
                    await asyncio.sleep(2 ** attempt)
            logger.error(
                "search() exhausted retries for %s — returning empty results: %s",
                q.question_id, last_exc,
            )
            return {"results": [], "related": []}

        async def evaluate(q: EvalQuestion) -> RetrievalResult:
            async with sem:
                t_start = time.monotonic()
                raw = await _search_with_retry(q)
                results_list = (
                    raw.get("results", raw) if isinstance(raw, dict) else raw
                )
                related_list: list[dict] = (
                    raw.get("related", []) if isinstance(raw, dict) else []
                )
                retrieval_latency_ms = (time.monotonic() - t_start) * 1000

                memory_contents: list[str] = []
                retrieved_sessions: set[str] = set()

                def _absorb(mem_obj: dict) -> None:
                    content = mem_obj.get("content")
                    if content:
                        memory_contents.append(content)
                    sid = (mem_obj.get("metadata") or {}).get("session_id")
                    if sid is not None:
                        retrieved_sessions.add(str(sid))

                for r in results_list:
                    _absorb(r.get("memory", {}))
                for r in related_list:
                    _absorb(r)

                relevance_scores = [
                    r.get("relevance_score", 0.0) for r in results_list
                ]
                r_at_k_correct, r_at_k_recall = _evidence_recall(
                    q.evidence, retrieved_sessions
                )

                generated = ""
                qa_correct = False
                qa_conf = 0.0
                try:
                    generated = await judge.generate_answer(
                        q.question, memory_contents
                    )
                    qa_correct, qa_conf = await judge.judge_correctness(
                        q.question, q.ground_truth, generated
                    )
                except Exception as e:
                    logger.warning(
                        "QA judge failed for %s: %s — treating as incorrect",
                        q.question_id,
                        e,
                    )

                total_latency_ms = (time.monotonic() - t_start) * 1000

                # Headline metric is QA accuracy → use ``is_correct`` for
                # QA. Stash R@k on side attributes for the aggregator.
                result = RetrievalResult(
                    question_id=q.question_id,
                    question=q.question,
                    ground_truth=q.ground_truth,
                    category=q.category,
                    retrieved_memories=memory_contents,
                    generated_answer=generated,
                    is_correct=qa_correct,
                    confidence=qa_conf,
                    relevance_scores=relevance_scores,
                    latency_ms=total_latency_ms,
                )
                result.r_at_k_correct = r_at_k_correct  # type: ignore[attr-defined]
                result.r_at_k_recall = r_at_k_recall  # type: ignore[attr-defined]
                result.retrieval_latency_ms = retrieval_latency_ms  # type: ignore[attr-defined]
                return result

        tasks: list = []
        for scenario in scenarios:
            for q in scenario.questions:
                tasks.append(evaluate(q))

        logger.info(
            "Evaluating %d LoCoMo questions end-to-end (retrieve + generate + judge)...",
            len(tasks),
        )
        results: list[RetrievalResult] = await asyncio.gather(*tasks)

        question_index: dict[str, EvalQuestion] = {
            q.question_id: q
            for scenario in scenarios
            for q in scenario.questions
        }

        # Exclude empty-evidence questions from the headline denominator
        # for parity with the R@k benchmark — same scorable set so the
        # two numbers compare on the same denominator.
        scorable: list[RetrievalResult] = []
        for r in results:
            q = question_index.get(r.question_id)
            if q is None:
                continue
            if _evidence_to_sessions(q.evidence):
                scorable.append(r)

        correct = sum(1 for r in scorable if r.is_correct)
        accuracy = (correct / len(scorable)) if scorable else 0.0
        avg_confidence = (
            sum(r.confidence for r in scorable) / len(scorable)
            if scorable
            else 0.0
        )
        by_category = compute_accuracy_by_category(scorable)
        avg_latency = (
            sum(r.latency_ms for r in results) / len(results)
            if results
            else 0.0
        )
        avg_retrieval_latency = (
            sum(
                getattr(r, "retrieval_latency_ms", r.latency_ms)
                for r in results
            )
            / len(results)
            if results
            else 0.0
        )

        # R@k cross-check on the same scorable set.
        r_at_k_correct = sum(
            1 for r in scorable if getattr(r, "r_at_k_correct", False)
        )
        r_at_k_accuracy = (
            r_at_k_correct / len(scorable) if scorable else 0.0
        )
        avg_recall = (
            sum(getattr(r, "r_at_k_recall", 0.0) for r in scorable)
            / len(scorable)
            if scorable
            else 0.0
        )

        return BenchmarkResult(
            benchmark_name=self.benchmark_name,
            dataset_name=self.dataset_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_questions=len(scorable),
            correct=correct,
            accuracy=accuracy,
            accuracy_by_category={
                cat: info["accuracy"] for cat, info in by_category.items()
            },
            avg_latency_ms=avg_latency,
            retrieval_metrics={
                "avg_top1_relevance": (
                    sum(
                        r.relevance_scores[0]
                        for r in results
                        if r.relevance_scores
                    )
                    / len(results)
                    if results
                    else 0.0
                ),
                "avg_judge_confidence": avg_confidence,
                # Same retrieval pipeline as locomo R@k bench — surfacing
                # both lets a reviewer verify the QA gain isn't an
                # artefact of a different retrieval path.
                "session_recall_at_k": r_at_k_accuracy,
                "avg_recall_at_k": avg_recall,
                "avg_retrieval_latency_ms": avg_retrieval_latency,
                "no_evidence_excluded": len(results) - len(scorable),
            },
            individual_results=results,
            config={
                "eval_version": self.eval_version,
                "mode": "raw_production_mirror",
                "metric": "end_to_end_qa_accuracy",
                "search_top_k": self.settings.search_top_k,
                "concurrency": self.settings.concurrency,
                "weight_recency": self.settings.weight_recency,
                "weight_importance": self.settings.weight_importance,
                "weight_relevance": self.settings.weight_relevance,
                "prev_turns": self.prev_turns,
                "next_turns": self.next_turns,
                "llm_model": self.settings.llm_model,
                "llm_thinking": self.settings.llm_thinking,
                "llm_temperature": self.settings.llm_temperature,
                "llm_top_p": self.settings.llm_top_p,
                "num_scenarios": len(scenarios),
                "adversarial_excluded": len(results) - len(scorable),
            },
        )
