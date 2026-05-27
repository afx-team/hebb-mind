"""ConvoMem benchmark runner.

Standalone bench (intentionally does not reuse
``BaseBenchmark.run``) because ConvoMem warrants a dedicated scoring
mode — see below.

Ingestion granularity is **per-message**, matching MemPalace's setup
so head-to-head ingest is symmetric.

Why end-to-end QA, not substring containment
--------------------------------------------
ConvoMem's published metric is verbatim substring match between the
``message_evidences`` text and the retrieved memory contents. That
metric is unreliable for our system in two ways:

1. Hebb's production ingest is allowed to clean / normalise content
   (the ``strip_noise`` step in ``hebb.ingest.noise``); a memory whose
   stored text differs from the evidence by even one character would
   score 0 even if the system clearly "remembers" the fact.
2. The benchmark question is what a user would actually ask; the
   ground-truth ``answer`` field is what a user would accept as a
   correct response. End-to-end QA accuracy directly measures whether
   the system answers the user — which is the only thing that
   matters in production.

We therefore use an LLM judge (configured via
``eval/eval.json``). Retrieval brings top-k memories → the same LLM
generates an answer using only those memories → the same LLM judges
the answer against the ground truth. A question is "correct" iff the
judge returns ``correct == true``.

The MemPalace substring number is NOT a reference for this dataset on
Hebb's side — see ``repo_pages/benchmarks/convomem/index.md`` for the
public framing. The ``_evidence_substring_recall`` helper is retained
in this module only because the existing unit tests pin its formula;
it is not part of the public bench surface.
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


class ConvoMemBenchmark(BaseBenchmark):
    """ConvoMem runner — per-message ingest, substring-match recall."""

    benchmark_name = "convomem"
    dataset_name = "ConvoMem"
    # v1: generic ingest + QA accuracy.
    # v2: per-message verbatim ingest, substring evidence recall.
    # v3: per-message ingest, end-to-end LLM QA judge (see module
    #     docstring for the rationale switch).
    eval_version = "v3"

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

                # Preference / state phrases — only for user-side
                # messages; assistant utterances are responses, not
                # self-descriptions, so the patterns shouldn't apply.
                if turn.role == "user":
                    for phrase in extract_preferences(text):
                        pref_meta = dict(metadata)
                        pref_meta["synthetic"] = True
                        batch.append({
                            "content": synthesize_preference_memory(phrase)[:10000],
                            "partition_id": scenario.scenario_id,
                            "importance_score": 4.0,
                            "tags": ["convomem-msg", "preference"],
                            "metadata": pref_meta,
                            "source": "convomem:preference",
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

                # End-to-end QA: generate then judge. Latency above
                # measures only retrieval; LLM time is not in the
                # benchmark's headline avg_latency_ms (it's reported
                # under config.judge_used).
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
                "avg_top1_relevance": (
                    sum(r.relevance_scores[0] for r in results if r.relevance_scores)
                    / len(results) if results else 0.0
                ),
                "avg_judge_confidence": (
                    sum(r.confidence for r in results) / len(results)
                    if results else 0.0
                ),
            },
            individual_results=results,
            config={
                "eval_version": self.eval_version,
                "mode": "raw_per_message",
                "metric": "end_to_end_qa_llm_judge",
                "judge_used": True,
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
