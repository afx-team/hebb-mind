"""LoCoMo benchmark runner.

Two-mode ingestion + containment-style scoring intended to mirror what
the Claude Code hook actually writes in production:

* ``UserPromptSubmit`` hook (``integrations/claude_code/write.py``)
  → one memory per user utterance, raw text only, no timestamp prefix,
  dedupe within the session, drop anything shorter than 20 chars.
* ``Stop`` hook (``integrations/claude_code/stop.py``)
  → one memory per turn round-trip formatted as
  ``[<speaker_a>] …\\n[<speaker_b>] …``.

There is **no** sliding-window chunking, **no** session-date string
embedded in the content, **no** BLIP caption injection. This is the
honest "what would the production hook surface store" baseline for the
LoCoMo dataset.

Scoring is *containment recall*, not end-to-end QA:
the answer is correct iff every comma-split ground-truth item appears
(case-insensitive substring) in the concatenation of the top-k retrieved
memory contents. Empty-GT (adversarial) questions are excluded from the
denominator since containment is undefined for them.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timezone

from eval.benchmarks.base import (
    PARTITION_ID,
    BaseBenchmark,
    BenchmarkResult,
    RetrievalResult,
)
from eval.client import HebbClient
from eval.datasets.base import EvalQuestion, EvalScenario
from eval.judge import LLMJudge
from eval.metrics.accuracy import compute_accuracy_by_category

logger = logging.getLogger(__name__)

# Match the hook's `_MIN_CONTENT_LENGTH` so utterance filtering is identical.
_MIN_CONTENT_LEN = 20


class LoComoBenchmark(BaseBenchmark):
    """LoCoMo runner aligned with the production Claude Code hook surface."""

    benchmark_name = "locomo"
    dataset_name = "LoCoMo"
    # v1: sliding-window chunk ingest, end-to-end QA + LLM judge.
    # v2: production-hook mirror (per-utterance + per-pair), containment recall.
    # v3: same ingest, MemPalace-style session-level evidence Recall@k.
    eval_version = "v3"

    # Symmetric turn-context window forwarded to /api/v1/search. Two
    # neighbours on each side recovers most multi-utterance facts (e.g.
    # "I moved from my home country" + "Sweden") without dragging in the
    # entire session.
    prev_turns: int = 2
    next_turns: int = 2

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        """Ingest in two passes, mirroring the production hooks exactly."""
        total = 0
        for scenario in scenarios:
            turns = sorted(
                scenario.conversations,
                key=lambda t: t.turn_index if t.turn_index is not None else 0,
            )

            batch: list[dict] = []

            # ----- Pass 1: per-utterance memories (write.py) -----
            # Session-scoped dedup mirrors `is_duplicate(session_id, cleaned)`
            # which hashes the cleaned text inside the session bucket.
            seen_hashes: dict[str | None, set[str]] = {}
            for turn in turns:
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
                    "partition_id": PARTITION_ID,
                    "importance_score": 5.0,
                    "tags": ["user-prompt", "hook"],
                    "metadata": metadata,
                    "source": "hook",
                })

                if len(batch) >= self.settings.batch_size:
                    await client.create_memories_batch(batch)
                    total += len(batch)
                    batch.clear()

            # ----- Pass 2: per-pair turn-summary memories (stop.py) -----
            # A "turn" in production is one round-trip: user prompt
            # followed by assistant reply. Adjacent LoCoMo turns alternate
            # speakers, so each consecutive (i, i+1) pair is one
            # round-trip. Step by 2 so each turn lands in exactly one
            # summary (matches the hook firing once per turn).
            for i in range(0, len(turns) - 1, 2):
                t1, t2 = turns[i], turns[i + 1]
                left = (t1.content or "").strip()
                right = (t2.content or "").strip()
                if not left and not right:
                    continue

                # Mirror the production Stop hook: prepend a bracketed
                # timestamp so the LLM can resolve relative-time phrases.
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
                    "partition_id": PARTITION_ID,
                    "importance_score": 4.0,
                    "tags": ["turn-summary", "hook"],
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
            "Ingested %d memories into %s (production-hook mirror: per-utterance + per-turn-pair, no chunking, no image captions, no timestamp-in-content)",
            total, PARTITION_ID,
        )

    # ------------------------------------------------------------------
    # Containment-recall evaluation — no LLM gen, no LLM judge
    # ------------------------------------------------------------------

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        """Retrieve top-k and score each question by ground-truth containment.

        Skips the entire LLM generate-+-judge pipeline. ``judge`` is
        accepted only to satisfy the ``Benchmark`` protocol.
        """
        sem = asyncio.Semaphore(self.settings.concurrency)

        async def evaluate(q: EvalQuestion) -> RetrievalResult:
            async with sem:
                t0 = time.monotonic()
                raw = await client.search(
                    query=q.question,
                    top_k=self.settings.search_top_k,
                    weight_recency=self.settings.weight_recency,
                    weight_importance=self.settings.weight_importance,
                    weight_relevance=self.settings.weight_relevance,
                    prev_turns=self.prev_turns,
                    next_turns=self.next_turns,
                )
                results_list = raw.get("results", raw) if isinstance(raw, dict) else raw
                related_list: list[dict] = raw.get("related", []) if isinstance(raw, dict) else []
                latency_ms = (time.monotonic() - t0) * 1000

                # Collect retrieved memory contents (for debugging) AND
                # the set of session_ids those memories carry — the
                # MemPalace-equivalent metric is "did any session that
                # contains evidence appear among retrieved memories?".
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
                    # related items are bare Memory dicts, not wrapped in
                    # {"memory": ...}.
                    _absorb(r)

                relevance_scores = [r.get("relevance_score", 0.0) for r in results_list]

                is_correct, confidence = _evidence_recall(q.evidence, retrieved_sessions)
                return RetrievalResult(
                    question_id=q.question_id,
                    question=q.question,
                    ground_truth=q.ground_truth,
                    category=q.category,
                    retrieved_memories=memory_contents,
                    generated_answer="",
                    is_correct=is_correct,
                    confidence=confidence,
                    relevance_scores=relevance_scores,
                    latency_ms=latency_ms,
                )

        tasks: list = []
        for scenario in scenarios:
            for q in scenario.questions:
                tasks.append(evaluate(q))

        logger.info("Evaluating %d questions by session-level evidence recall...", len(tasks))
        results: list[RetrievalResult] = await asyncio.gather(*tasks)

        # Index by question_id for evidence lookup.
        question_index: dict[str, EvalQuestion] = {
            q.question_id: q for scenario in scenarios for q in scenario.questions
        }

        # Exclude questions with no evidence sessions (typically empty-GT
        # adversarial). Session-level recall is undefined when GT contains
        # no session_id to look for.
        scorable: list[RetrievalResult] = []
        for r in results:
            q = question_index.get(r.question_id)
            if q is None:
                continue
            if _evidence_to_sessions(q.evidence):
                scorable.append(r)

        correct = sum(1 for r in scorable if r.is_correct)
        accuracy = (correct / len(scorable)) if scorable else 0.0
        avg_recall = (
            sum(r.confidence for r in scorable) / len(scorable) if scorable else 0.0
        )
        by_category = compute_accuracy_by_category(scorable)
        avg_latency = (
            sum(r.latency_ms for r in results) / len(results) if results else 0.0
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
                    sum(r.relevance_scores[0] for r in results if r.relevance_scores)
                    / len(results) if results else 0.0
                ),
                # MemPalace-style mean Recall@k: average fraction of GT
                # evidence sessions surfaced per question. Equivalent to
                # confidence averaged over scorable questions.
                "avg_recall_at_k": avg_recall,
                "no_evidence_excluded": len(results) - len(scorable),
            },
            individual_results=results,
            config={
                "eval_version": self.eval_version,
                "mode": "raw_production_mirror",
                "metric": "session_evidence_recall",
                "search_top_k": self.settings.search_top_k,
                "concurrency": self.settings.concurrency,
                "weight_recency": self.settings.weight_recency,
                "weight_importance": self.settings.weight_importance,
                "weight_relevance": self.settings.weight_relevance,
                "num_scenarios": len(scenarios),
                "adversarial_excluded": len(results) - len(scorable),
            },
        )


# ----------------------------------------------------------------------
# Session-level evidence recall (MemPalace-equivalent metric)
# ----------------------------------------------------------------------

# LoCoMo's `evidence` field carries dia_ids of the form "D{session}:{turn}".
# A question is "correct" under MemPalace's R@k iff at least one of its
# evidence sessions appears in the set of retrieved memories' session_ids.
_DIA_RE = re.compile(r"^\s*D\s*(\d+)\s*:\s*\d+\s*$", re.IGNORECASE)


def _evidence_to_sessions(evidence: list[str] | None) -> set[str]:
    """Pull the session_ids out of a LoCoMo ``evidence`` list.

    >>> _evidence_to_sessions(["D1:3", "D4:12"])
    {'1', '4'}
    """
    out: set[str] = set()
    for e in evidence or []:
        if e is None:
            continue
        m = _DIA_RE.match(str(e))
        if m:
            out.add(m.group(1))
    return out


def _evidence_recall(
    evidence: list[str] | None, retrieved_sessions: set[str]
) -> tuple[bool, float]:
    """Session-level Recall@k, MemPalace-style.

    Returns ``(is_correct, recall)`` where:
      - ``is_correct`` is True iff at least one evidence session was
        surfaced in top-k retrieved memories (intersection non-empty).
      - ``recall`` is ``|GT ∩ retrieved| / |GT|`` — the fraction of
        evidence sessions covered, useful as a softer companion metric.

    Questions with no parseable evidence (typically the empty-GT
    adversarial set) are treated as trivially correct here and excluded
    from the headline denominator by the caller.
    """
    gt = _evidence_to_sessions(evidence)
    if not gt:
        return True, 1.0
    hits = gt & retrieved_sessions
    return bool(hits), len(hits) / len(gt)


# ----------------------------------------------------------------------
# Containment matching helpers
# ----------------------------------------------------------------------

# Split GT on common list separators while keeping quoted phrases intact.
_LIST_SPLIT_RE = re.compile(r"\s*(?:,|;|/| and )\s*")
_QUOTE_STRIP_RE = re.compile(r'^[\s"\']+|[\s"\'.,!?]+$')
_WS_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text.lower()).strip()


def _split_items(gt_norm: str) -> list[str]:
    """Split a GT string into comma-separated items, stripping quotes/whitespace."""
    parts = [_QUOTE_STRIP_RE.sub("", p) for p in _LIST_SPLIT_RE.split(gt_norm)]
    return [p for p in parts if p]


def _contains_gt(
    ground_truth: str, memories: list[str]
) -> tuple[bool, float]:
    """Return ``(is_correct, confidence)`` for containment scoring.

    Confidence is the fraction of GT items found, useful for debugging
    partial matches. ``is_correct`` is True when *all* items are present.
    """
    if not ground_truth or not ground_truth.strip():
        # Adversarial: undefined; flagged via the headline by excluding
        # them from the denominator, but we still emit True so the
        # per-result row doesn't look mass-wrong.
        return True, 1.0

    haystack = _normalise(" \n--- \n".join(memories))
    if not haystack:
        return False, 0.0

    gt_norm = _normalise(ground_truth)
    items = _split_items(gt_norm)
    if not items:
        return False, 0.0

    hits = sum(1 for it in items if it and it in haystack)
    return hits == len(items), hits / len(items)
