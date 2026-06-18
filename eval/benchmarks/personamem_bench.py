"""PersonaMem benchmark runner (multiple-choice personalization).

PersonaMem's ground truth is a clean MCQ letter, so — like MemBench —
this bench does NOT use the free-text LLM judge. It retrieves the
user's relevant conversation history, asks the reader to pick the best
lettered option, and scores exact-match on the letter. No clean
retrieval-evidence id exists (the answer is spread across the persona's
history), so there is no Recall@k; the headline is MCQ accuracy, broken
out by the dataset's seven question types.

Isolation mirrors MemBench: each ``(context, end_index)`` scenario gets
its own partition holding exactly ``turns[:end_index]``, and retrieval
is partition-scoped — so a question never retrieves another persona's
turns or future turns of its own conversation.
"""

from __future__ import annotations

import asyncio
import logging
import re
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

# Pull the chosen letter out of the reader's reply. The reader is told to
# answer "(a)"; we prefer the LAST parenthesised letter (so a reply that
# echoes options before concluding picks the conclusion), then fall back to
# the last standalone single-letter token ("c", "answer: d") — which never
# matches a letter embedded in a word like the "o" in "option".
_PAREN_LETTER_RE = re.compile(r"\(([a-zA-Z])\)")
_TOKEN_LETTER_RE = re.compile(r"(?<![a-zA-Z])([a-zA-Z])(?![a-zA-Z])")


def parse_choice(text: str, valid: set[str]) -> str | None:
    """Parse the chosen option letter from the reader's reply.

    ``valid`` is the set of letters that label real options for this
    question (always {'a','b','c','d'} for PersonaMem). Returns the
    lowercased letter, or ``None`` if no valid letter can be recovered.
    """
    if not text:
        return None
    # 1. Last "(x)" whose letter is a real option.
    for m in reversed(list(_PAREN_LETTER_RE.finditer(text))):
        if m.group(1).lower() in valid:
            return m.group(1).lower()
    # 2. Last standalone single-letter token that is a real option.
    for m in reversed(list(_TOKEN_LETTER_RE.finditer(text))):
        if m.group(1).lower() in valid:
            return m.group(1).lower()
    return None


async def _ensure_partition(client: HebbClient, partition_id: str) -> None:
    """Create the partition (idempotent — swallow already-exists errors)."""
    try:
        await client.create_partition(partition_id, name=partition_id)
    except Exception:
        pass


async def _ingest_batch_with_retry(client: HebbClient, batch: list[dict]) -> None:
    """POST a memory batch, retrying transient HTTP errors.

    Ingest is sequential, but on a loaded machine an embedding batch can
    momentarily exceed the client read timeout; an un-retried timeout here
    aborts the whole run before a single question is scored. Retry a few
    times with backoff, then re-raise.
    """
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            await client.create_memories_batch(batch)
            return
        except Exception as e:
            last_err = e
            logger.warning(
                "ingest batch failed (attempt %d/4, n=%d): %s — retrying",
                attempt + 1, len(batch), str(e)[:120],
            )
            await asyncio.sleep(3 * (attempt + 1))
    assert last_err is not None
    raise last_err


class PersonaMemBenchmark(BaseBenchmark):
    """PersonaMem runner — per-cut-point partition ingest, MCQ letter accuracy."""

    benchmark_name = "personamem"
    dataset_name = "PersonaMem"
    # v1: per-(context,end_index) partition ingest, partition-scoped
    # retrieval, exact-match MCQ accuracy (no free-text LLM judge).
    eval_version = "v1"

    def _format_turn(self, turn) -> str:
        return f"[Turn {turn.turn_index}] {turn.role}: {turn.content}"

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        """Ingest each scenario's conversation prefix into its own partition."""
        total = 0
        for scenario in scenarios:
            await _ensure_partition(client, scenario.scenario_id)
            batch: list[dict] = []
            for turn in scenario.conversations:
                content = self._format_turn(turn).strip()
                if not content:
                    continue
                batch.append({
                    "content": content[:10000],
                    "partition_id": scenario.scenario_id,
                    "importance_score": 5.0,
                    "tags": ["personamem-turn"],
                    "metadata": {"turn": turn.turn_index},
                    "source": "personamem",
                })
                if len(batch) >= self.settings.batch_size:
                    await _ingest_batch_with_retry(client, batch)
                    total += len(batch)
                    batch.clear()
            if batch:
                await _ingest_batch_with_retry(client, batch)
                total += len(batch)

        logger.info(
            "Ingested %d PersonaMem turns across %d per-cut-point partitions",
            total, len(scenarios),
        )

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        """Retrieve partition-scoped, pick an option, score MCQ accuracy."""
        sem = asyncio.Semaphore(self.settings.concurrency)

        async def _search_with_retry(scenario_id: str, query: str) -> dict | list:
            """Search the scenario's partition, retrying transient HTTP errors.

            A single slow/stuck search must not abort the whole 589-question
            run (an un-retried ``httpx.ReadTimeout`` propagating through
            ``asyncio.gather`` is what killed an earlier run mid-way). Retry a
            few times with backoff, then re-raise so the caller records the
            question as an error rather than crashing.
            """
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    return await client.search(
                        query=query,
                        partition_ids=[scenario_id],
                        top_k=self.settings.search_top_k,
                        weight_recency=self.settings.weight_recency,
                        weight_importance=self.settings.weight_importance,
                        weight_relevance=self.settings.weight_relevance,
                    )
                except Exception as e:  # httpx timeouts / transient server load
                    last_err = e
                    logger.warning(
                        "search failed (attempt %d/3) for %s: %s — retrying",
                        attempt + 1, scenario_id, str(e)[:120],
                    )
                    await asyncio.sleep(2 * (attempt + 1))
            assert last_err is not None
            raise last_err

        async def evaluate(
            scenario_id: str, q: EvalQuestion
        ) -> tuple[RetrievalResult, bool, bool]:
            options: list[str] = [str(o) for o in q.metadata.get("options", [])]
            gold = q.metadata.get("answer_letter")
            valid = {
                o.strip()[1].lower()
                for o in options
                if len(o.strip()) > 2 and o.strip()[0] == "("
            }
            async with sem:
                t0 = time.monotonic()
                try:
                    raw = await _search_with_retry(scenario_id, q.question)
                    results_list = raw.get("results", raw) if isinstance(raw, dict) else raw
                    related_list = raw.get("related", []) if isinstance(raw, dict) else []

                    memory_contents = [r["memory"]["content"] for r in results_list]
                    memory_contents.extend(
                        r["content"] for r in related_list if r.get("content")
                    )
                    relevance_scores = [r.get("relevance_score", 0.0) for r in results_list]

                    reply = await judge.select_choice(q.question, memory_contents, options)
                    chosen = parse_choice(reply, valid)
                except Exception as e:
                    # Unrecoverable retrieval/reader error — score the question
                    # wrong (it was not answered) but keep the run alive and
                    # count it so a corrupted number is never read as a memory
                    # result.
                    logger.error("evaluate failed for %s: %s", q.question_id, str(e)[:160])
                    return (
                        RetrievalResult(
                            question_id=q.question_id, question=q.question,
                            ground_truth=q.ground_truth, category=q.category,
                            retrieved_memories=[],
                            generated_answer=f"(error) {type(e).__name__}: {str(e)[:120]}",
                            is_correct=False, confidence=0.0, relevance_scores=[],
                            latency_ms=(time.monotonic() - t0) * 1000,
                        ),
                        False,
                        True,
                    )

                latency_ms = (time.monotonic() - t0) * 1000
                is_valid = chosen is not None
                is_correct = is_valid and chosen == gold

                if is_valid:
                    chosen_text = next(
                        (o for o in options if o.strip()[1:2].lower() == chosen),
                        f"({chosen})",
                    )
                    generated = chosen_text
                else:
                    generated = f"(no valid letter) {reply[:150]}"

                return (
                    RetrievalResult(
                        question_id=q.question_id,
                        question=q.question,
                        ground_truth=q.ground_truth,
                        category=q.category,
                        retrieved_memories=memory_contents,
                        generated_answer=generated,
                        is_correct=is_correct,
                        confidence=1.0 if is_correct else 0.0,
                        relevance_scores=relevance_scores,
                        latency_ms=latency_ms,
                    ),
                    is_valid,
                    False,
                )

        tasks = [
            evaluate(scenario.scenario_id, q)
            for scenario in scenarios
            for q in scenario.questions
        ]
        logger.info("Evaluating %d PersonaMem questions by MCQ accuracy...", len(tasks))
        paired = await asyncio.gather(*tasks)
        results = [p[0] for p in paired]
        error_count = sum(1 for p in paired if p[2])
        if error_count:
            logger.warning(
                "%d/%d questions errored (retrieval/reader) and were scored wrong",
                error_count, len(paired),
            )

        correct = sum(1 for r in results if r.is_correct)
        accuracy = (correct / len(results)) if results else 0.0
        by_category = compute_accuracy_by_category(results)
        avg_latency = (
            sum(r.latency_ms for r in results) / len(results) if results else 0.0
        )
        # Fraction of replies from which a valid option letter was parsed —
        # a low number flags a reader/format problem, not a memory problem.
        valid_choice_rate = (
            sum(1 for p in paired if p[1]) / len(paired) if paired else 0.0
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
                "valid_choice_rate": valid_choice_rate,
                "error_rate": (error_count / len(paired)) if paired else 0.0,
                "avg_top1_relevance": (
                    sum(r.relevance_scores[0] for r in results if r.relevance_scores)
                    / len(results)
                    if results
                    else 0.0
                ),
            },
            individual_results=results,
            config={
                "eval_version": self.eval_version,
                "metric": "mcq_letter_accuracy",
                # PersonaMem ships as v1 (32k, ~589 q, ``all_options`` schema)
                # and a newer v2 (~5000 q). We run v1-32k. Stamped here so the
                # report self-documents which dataset variant the number is on
                # — distinct from ``eval_version`` (the sticky *methodology*
                # version), which the renderer also prints.
                "dataset_variant": "personamem-v1-32k",
                "num_questions": len(results),
                "num_options": 4,
                "random_baseline": 0.25,
                "mode": self.settings.mode.value,
                "llm_model": self.settings.llm_model,
                "llm_thinking": self.settings.llm_thinking,
                "llm_temperature": 0.0,
                "search_top_k": self.settings.search_top_k,
                "concurrency": self.settings.concurrency,
                "weight_recency": self.settings.weight_recency,
                "weight_importance": self.settings.weight_importance,
                "weight_relevance": self.settings.weight_relevance,
                "num_scenarios": len(scenarios),
            },
        )
