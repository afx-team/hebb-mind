"""Unit tests for the LongMemEval adapter and benchmark.

Adapter tests use synthetic in-memory data (no HuggingFace downloads).
Benchmark tests mock ``HebbClient.search`` so no server is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eval.benchmarks.longmemeval_bench import LongMemEvalBenchmark
from eval.config import EvalSettings
from eval.datasets.base import EvalQuestion, EvalScenario
from eval.datasets.longmemeval import LongMemEvalAdapter


# ---------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------


def _write_lme_fixture(tmp_path: Path) -> Path:
    """Two-session conversation with a single question whose evidence is session 'A'."""
    payload = [
        {
            "question_id": "q-001",
            "question_type": "multi-session",
            "question": "Where did the user go for vacation?",
            "answer": "Hawaii",
            "question_date": "2023-04-26 (Wed) 10:55",
            "haystack_session_ids": ["A", "B"],
            "haystack_dates": ["2023-04-01", "2023-04-15"],
            "answer_session_ids": ["A"],
            "haystack_sessions": [
                [
                    {"role": "user", "content": "Booked flights to Hawaii for July."},
                    {"role": "assistant", "content": "Nice, when are you flying out?"},
                ],
                [
                    {"role": "user", "content": "Watching a movie tonight."},
                    {"role": "assistant", "content": "Enjoy!"},
                ],
            ],
        }
    ]
    fpath = tmp_path / "lme.json"
    fpath.write_text(json.dumps(payload))
    return fpath


def test_lme_adapter_parses_sessions_and_answer_ids(tmp_path: Path) -> None:
    fpath = _write_lme_fixture(tmp_path)
    scenarios = LongMemEvalAdapter().load(fpath)

    assert len(scenarios) == 1
    s = scenarios[0]
    assert s.scenario_id == "longmemeval_q-001"

    # 2 sessions × 2 turns each = 4 ConversationTurns, session_id preserved
    assert len(s.conversations) == 4
    assert [t.session_id for t in s.conversations] == ["A", "A", "B", "B"]
    assert [t.role for t in s.conversations] == ["user", "assistant", "user", "assistant"]
    assert [t.turn_index for t in s.conversations] == [0, 1, 2, 3]
    assert s.conversations[0].timestamp == "2023-04-01"
    assert s.conversations[2].timestamp == "2023-04-15"

    # answer_session_ids must reach EvalQuestion.metadata for the bench
    assert len(s.questions) == 1
    q = s.questions[0]
    assert q.category == "multi-session"
    assert q.metadata["answer_session_ids"] == ["A"]
    assert q.evidence == ["A"]
    assert q.metadata["question_date"] == "2023-04-26 (Wed) 10:55"


def test_lme_adapter_skips_items_without_question_or_turns(tmp_path: Path) -> None:
    payload = [
        {"question_id": "no-q", "haystack_sessions": [[{"role": "user", "content": "hi"}]]},
        {"question_id": "no-turns", "question": "?", "haystack_sessions": []},
    ]
    fpath = tmp_path / "lme.json"
    fpath.write_text(json.dumps(payload))
    assert LongMemEvalAdapter().load(fpath) == []


# ---------------------------------------------------------------------
# Benchmark — session-level R@k scoring
# ---------------------------------------------------------------------


def _build_scenario(answer_sids: list[str]) -> EvalScenario:
    q = EvalQuestion(
        question_id="lme-q-1",
        question="Where did user go for vacation?",
        ground_truth="Hawaii",
        category="multi-session",
        evidence=answer_sids,
        metadata={"answer_session_ids": answer_sids},
    )
    return EvalScenario(
        scenario_id="lme-q-1",
        conversations=[],  # ingest is not exercised in scoring tests
        questions=[q],
    )


def _mock_search_response(session_ids_in_order: list[str]) -> dict:
    """Build a fake /api/v1/search response.

    Each retrieved memory carries one session_id in its metadata, so the
    bench's ``ranked_sessions`` reconstruction sees the same order.
    """
    return {
        "results": [
            {
                "memory": {
                    "content": f"memory text for session {sid}",
                    "metadata": {"session_id": sid},
                },
                "relevance_score": 1.0 - (i * 0.05),
            }
            for i, sid in enumerate(session_ids_in_order)
        ],
        "related": [],
    }


@pytest.mark.asyncio
async def test_lme_bench_recall_any_hits_when_evidence_in_topk() -> None:
    """If any answer_session_id is in top-K, recall_any@k = 1.0."""
    scenarios = [_build_scenario(answer_sids=["A"])]
    settings = EvalSettings(search_top_k=10, concurrency=1)
    bench = LongMemEvalBenchmark(settings)

    client = AsyncMock()
    # 'A' shows up at rank 3 — should still hit recall_any@10
    client.search = AsyncMock(
        return_value=_mock_search_response(["X", "Y", "A", "Z", "Q"])
    )

    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]

    assert result.total_questions == 1
    assert result.correct == 1
    assert result.accuracy == 1.0
    assert result.retrieval_metrics["recall_any@10"] == 1.0
    assert result.retrieval_metrics["recall_any@5"] == 1.0
    # Rank-3 hit: NDCG@10 = 1 / log2(3+1) = 0.5
    assert pytest.approx(result.retrieval_metrics["ndcg@10"], rel=1e-3) == 0.5


@pytest.mark.asyncio
async def test_lme_bench_recall_any_misses_when_evidence_absent() -> None:
    scenarios = [_build_scenario(answer_sids=["A"])]
    settings = EvalSettings(search_top_k=10, concurrency=1)
    bench = LongMemEvalBenchmark(settings)

    client = AsyncMock()
    client.search = AsyncMock(
        return_value=_mock_search_response(["X", "Y", "Z"])
    )

    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    assert result.correct == 0
    assert result.retrieval_metrics["recall_any@10"] == 0.0
    assert result.retrieval_metrics["ndcg@10"] == 0.0


@pytest.mark.asyncio
async def test_lme_bench_recall_all_partial_hit() -> None:
    """recall_all@k credits the fraction of evidence sessions retrieved."""
    scenarios = [_build_scenario(answer_sids=["A", "B", "C"])]
    settings = EvalSettings(search_top_k=10, concurrency=1)
    bench = LongMemEvalBenchmark(settings)

    client = AsyncMock()
    # Retrieve 'A' and 'B' but not 'C'
    client.search = AsyncMock(
        return_value=_mock_search_response(["A", "B", "X", "Y", "Z"])
    )

    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    # any-hit → correct
    assert result.correct == 1
    # 2 of 3 evidence sessions surfaced
    assert pytest.approx(result.retrieval_metrics["recall_all@10"], rel=1e-3) == 2 / 3


@pytest.mark.asyncio
async def test_lme_bench_dedupes_repeated_session_ids() -> None:
    """Repeated session_ids in the result list count once for ranking position."""
    scenarios = [_build_scenario(answer_sids=["A"])]
    settings = EvalSettings(search_top_k=10, concurrency=1)
    bench = LongMemEvalBenchmark(settings)

    client = AsyncMock()
    # 'A' appears at ranks 0 (twice) — dedupe keeps it at rank 0
    client.search = AsyncMock(
        return_value=_mock_search_response(["A", "A", "B", "C"])
    )
    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    # NDCG@10 at rank 0 with 1 relevant: 1 / log2(0+2) = 1.0
    assert result.retrieval_metrics["ndcg@10"] == 1.0


@pytest.mark.asyncio
async def test_lme_bench_excludes_questions_without_evidence() -> None:
    """A question with empty answer_session_ids should not break the run."""
    q_with = EvalQuestion(
        question_id="q1",
        question="?",
        ground_truth="ok",
        category="x",
        evidence=["A"],
        metadata={"answer_session_ids": ["A"]},
    )
    q_without = EvalQuestion(
        question_id="q2",
        question="?",
        ground_truth="ok",
        category="x",
        evidence=[],
        metadata={"answer_session_ids": []},
    )
    scenarios = [
        EvalScenario(scenario_id="s1", conversations=[], questions=[q_with]),
        EvalScenario(scenario_id="s2", conversations=[], questions=[q_without]),
    ]
    settings = EvalSettings(search_top_k=10, concurrency=1)
    bench = LongMemEvalBenchmark(settings)

    client = AsyncMock()
    client.search = AsyncMock(return_value=_mock_search_response(["A"]))

    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    # Only the question with evidence is scorable
    assert result.total_questions == 1
    assert result.retrieval_metrics["no_evidence_excluded"] == 1
