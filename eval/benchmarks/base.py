"""Base types and shared benchmark runner logic."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from eval.client import HebbClient
from eval.config import EvalSettings
from eval.datasets.base import EvalQuestion, EvalScenario
from eval.judge import LLMJudge
from eval.metrics.accuracy import compute_accuracy, compute_accuracy_by_category

logger = logging.getLogger(__name__)

PARTITION_ID = "mem_hippocampus"


@dataclass
class RetrievalResult:
    """Result of a single retrieval + evaluation."""

    question_id: str
    question: str
    ground_truth: str
    category: str
    retrieved_memories: list[str]
    generated_answer: str
    is_correct: bool
    confidence: float
    relevance_scores: list[float]
    latency_ms: float


@dataclass
class BenchmarkResult:
    """Aggregate result for a complete benchmark run."""

    benchmark_name: str
    dataset_name: str
    timestamp: str
    total_questions: int
    correct: int
    accuracy: float
    accuracy_by_category: dict[str, float]
    avg_latency_ms: float
    retrieval_metrics: dict[str, float]
    individual_results: list[RetrievalResult]
    config: dict = field(default_factory=dict)


class Benchmark(Protocol):
    """Protocol for running a benchmark against hebb."""

    @property
    def name(self) -> str: ...

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None: ...

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult: ...


class BaseBenchmark:
    """Shared benchmark logic — ingest into mem_hippocampus, no tags."""

    benchmark_name: str = ""
    dataset_name: str = ""

    def __init__(self, settings: EvalSettings):
        self.settings = settings

    @property
    def name(self) -> str:
        return self.benchmark_name

    def _format_turn(self, turn) -> str:
        """Format a conversation turn for ingestion. Override for custom formatting."""
        session = turn.session_id
        if session:
            return (
                f"[Session {session}, Turn {turn.turn_index}] "
                f"{turn.role}: {turn.content}"
            )
        return f"[Turn {turn.turn_index}] {turn.role}: {turn.content}"

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        """Ingest conversation turns into mem_hebb. No tags, no custom partitions."""
        total = 0
        for scenario in scenarios:
            batch: list[dict] = []
            for turn in scenario.conversations:
                content = self._format_turn(turn)
                item: dict = {
                    "content": content[:10000],
                    "partition_id": PARTITION_ID,
                    "importance_score": 5.0,
                }
                metadata = {}
                if turn.session_id is not None:
                    metadata["session_id"] = str(turn.session_id)
                if turn.turn_index is not None:
                    metadata["turn"] = turn.turn_index
                if turn.timestamp is not None:
                    metadata["timestamp"] = turn.timestamp
                if metadata:
                    item["metadata"] = metadata
                batch.append(item)

                if len(batch) >= self.settings.batch_size:
                    await client.create_memories_batch(batch)
                    total += len(batch)
                    batch.clear()

            if batch:
                await client.create_memories_batch(batch)
                total += len(batch)

        logger.info("Ingested %d turns into %s", total, PARTITION_ID)

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        """Run all questions — search all partitions (no filter)."""
        sem = asyncio.Semaphore(self.settings.concurrency)

        async def evaluate_question(q: EvalQuestion) -> RetrievalResult:
            async with sem:
                t0 = time.monotonic()

                raw = await client.search(
                    query=q.question,
                    top_k=self.settings.search_top_k,
                    weight_recency=self.settings.weight_recency,
                    weight_importance=self.settings.weight_importance,
                    weight_relevance=self.settings.weight_relevance,
                )
                results_list = raw.get("results", raw) if isinstance(raw, dict) else raw
                related_list: list[dict] = raw.get("related", []) if isinstance(raw, dict) else []

                latency_ms = (time.monotonic() - t0) * 1000
                memory_contents = [r["memory"]["content"] for r in results_list]
                # Append graph-expanded related memories
                memory_contents.extend(r["content"] for r in related_list if r.get("content"))
                relevance_scores = [r.get("relevance_score", 0.0) for r in results_list]

                generated = await judge.generate_answer(q.question, memory_contents)
                is_correct, confidence = await judge.judge_correctness(
                    q.question, q.ground_truth, generated
                )

                return RetrievalResult(
                    question_id=q.question_id,
                    question=q.question,
                    ground_truth=q.ground_truth,
                    category=q.category,
                    retrieved_memories=memory_contents,
                    generated_answer=generated,
                    is_correct=is_correct,
                    confidence=confidence,
                    relevance_scores=relevance_scores,
                    latency_ms=latency_ms,
                )

        tasks = []
        for scenario in scenarios:
            for q in scenario.questions:
                tasks.append(evaluate_question(q))

        logger.info("Evaluating %d questions...", len(tasks))
        results = await asyncio.gather(*tasks)

        accuracy = compute_accuracy(results)
        by_category = compute_accuracy_by_category(results)
        avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0.0

        return BenchmarkResult(
            benchmark_name=self.benchmark_name,
            dataset_name=self.dataset_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_questions=len(results),
            correct=sum(1 for r in results if r.is_correct),
            accuracy=accuracy,
            accuracy_by_category={
                cat: info["accuracy"] for cat, info in by_category.items()
            },
            avg_latency_ms=avg_latency,
            retrieval_metrics={
                "avg_top1_relevance": (
                    sum(r.relevance_scores[0] for r in results if r.relevance_scores)
                    / len(results)
                    if results
                    else 0.0
                ),
            },
            individual_results=results,
            config={
                "llm_model": self.settings.llm_model,
                "llm_thinking": self.settings.llm_thinking,
                "llm_temperature": self.settings.llm_temperature,
                "llm_top_p": self.settings.llm_top_p,
                "mode": self.settings.mode.value,
                "search_top_k": self.settings.search_top_k,
                "concurrency": self.settings.concurrency,
                "weight_recency": self.settings.weight_recency,
                "weight_importance": self.settings.weight_importance,
                "weight_relevance": self.settings.weight_relevance,
                "num_scenarios": len(scenarios),
            },
        )
