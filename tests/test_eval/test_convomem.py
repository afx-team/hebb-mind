"""Unit tests for the ConvoMem adapter and benchmark.

Adapter tests synthesize the per-file ``evidence_items`` schema so no
HuggingFace download is needed. Benchmark tests mock ``HebbClient.search``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eval.benchmarks.convomem_bench import (
    ConvoMemBenchmark,
    _evidence_substring_recall,
)
from eval.config import EvalSettings
from eval.datasets.base import EvalQuestion, EvalScenario
from eval.datasets.convomem import ConvoMemAdapter


# ---------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------


def _write_convomem_fixture(tmp_path: Path) -> Path:
    """One item per evidence category (6 total), each with a 1-message evidence."""
    items: list[dict] = []
    for cat in (
        "user_evidence",
        "assistant_facts_evidence",
        "changing_evidence",
        "abstention_evidence",
        "preference_evidence",
        "implicit_connection_evidence",
    ):
        items.append({
            "_category_key": cat,
            "_source_file": f"core_benchmark/evidence_questions/{cat}/1_evidence/x.json",
            "conversations": [{
                "messages": [
                    {"speaker": "user", "text": f"{cat} user line"},
                    {"speaker": "assistant", "text": f"{cat} assistant line"},
                ]
            }],
            "question": f"q for {cat}",
            "answer": f"a for {cat}",
            "message_evidences": [{"text": f"{cat} user line"}],
        })
    fpath = tmp_path / "convomem.json"
    fpath.write_text(json.dumps(items))
    return fpath


def test_convomem_adapter_one_scenario_per_item_per_category(tmp_path: Path) -> None:
    fpath = _write_convomem_fixture(tmp_path)
    scenarios = ConvoMemAdapter(per_category=100).load(fpath)
    assert len(scenarios) == 6

    categories = {s.questions[0].category for s in scenarios}
    assert categories == {
        "user_evidence",
        "assistant_facts_evidence",
        "changing_evidence",
        "abstention_evidence",
        "preference_evidence",
        "implicit_connection_evidence",
    }

    # Spot-check first scenario
    s = scenarios[0]
    assert len(s.conversations) == 2
    assert [t.role for t in s.conversations] == ["user", "assistant"]
    assert s.conversations[0].content == "user_evidence user line"
    q = s.questions[0]
    assert q.evidence == ["user_evidence user line"]
    assert q.metadata["evidence_category"] == "user_evidence"


def test_convomem_adapter_skips_items_without_evidence_or_question(tmp_path: Path) -> None:
    items = [
        {"_category_key": "user_evidence", "conversations": [{"messages": []}],
         "question": "q", "message_evidences": []},
        {"_category_key": "user_evidence",
         "conversations": [{"messages": [{"speaker": "user", "text": "hi"}]}],
         "question": "", "message_evidences": [{"text": "hi"}]},
    ]
    fpath = tmp_path / "c.json"
    fpath.write_text(json.dumps(items))
    assert ConvoMemAdapter().load(fpath) == []


# ---------------------------------------------------------------------
# Substring recall (pure function)
# ---------------------------------------------------------------------


def test_substring_recall_perfect_match() -> None:
    evidence = ["The capital of France is Paris."]
    memories = ["I learned that the capital of france is paris.", "irrelevant"]
    assert _evidence_substring_recall(evidence, memories) == 1.0


def test_substring_recall_reverse_containment() -> None:
    """A retrieved memory shorter than the evidence still credits a match."""
    evidence = ["Paris is the capital of France"]
    memories = ["paris"]
    # 'paris' ⊂ evidence → credit
    assert _evidence_substring_recall(evidence, memories) == 1.0


def test_substring_recall_zero_when_absent() -> None:
    evidence = ["The user has two children."]
    memories = ["The user likes coffee.", "It rained yesterday."]
    assert _evidence_substring_recall(evidence, memories) == 0.0


def test_substring_recall_partial() -> None:
    evidence = ["alpha-fact", "beta-fact", "gamma-fact"]
    memories = ["found alpha-fact here", "and beta-fact"]
    assert pytest.approx(_evidence_substring_recall(evidence, memories), rel=1e-3) == 2 / 3


def test_substring_recall_empty_evidence_is_trivially_one() -> None:
    assert _evidence_substring_recall([], ["anything"]) == 1.0


def test_substring_recall_empty_memories_zero_when_evidence_present() -> None:
    assert _evidence_substring_recall(["x"], []) == 0.0


# ---------------------------------------------------------------------
# Benchmark — full run with mocked search
# ---------------------------------------------------------------------


def _scenario(category: str, evidence: list[str]) -> EvalScenario:
    return EvalScenario(
        scenario_id=f"s-{category}",
        conversations=[],
        questions=[EvalQuestion(
            question_id=f"q-{category}",
            question=f"question for {category}",
            ground_truth="",
            category=category,
            evidence=evidence,
            metadata={"evidence_category": category},
        )],
    )


def _mock_search(memory_texts: list[str]) -> dict:
    return {
        "results": [
            {
                "memory": {"content": t, "metadata": {}},
                "relevance_score": 1.0 - (i * 0.1),
            }
            for i, t in enumerate(memory_texts)
        ],
        "related": [],
    }


@pytest.mark.asyncio
async def test_convomem_bench_uses_llm_judge_per_question() -> None:
    """The bench drives an end-to-end QA loop, not substring matching."""
    scenarios = [
        _scenario("user_evidence", ["fact A"]),
        _scenario("user_evidence", ["fact B"]),
        _scenario("preference_evidence", ["fact C"]),
    ]
    settings = EvalSettings(search_top_k=5, concurrency=1)
    bench = ConvoMemBenchmark(settings)

    client = AsyncMock()
    client.search = AsyncMock(return_value=_mock_search(["any retrieved content"]))

    # Judge returns 2 of 3 correct.
    judge = AsyncMock()
    judge.generate_answer = AsyncMock(
        side_effect=["answer for A", "answer for B", "answer for C"]
    )
    judge.judge_correctness = AsyncMock(
        side_effect=[(True, 0.9), (False, 0.2), (True, 0.95)]
    )

    result = await bench.run(client, scenarios, judge)

    assert result.total_questions == 3
    assert result.correct == 2
    # Per-category aggregation reflects judge verdicts
    assert result.accuracy_by_category["user_evidence"] == 0.5  # 1/2
    assert result.accuracy_by_category["preference_evidence"] == 1.0  # 1/1
    # The judge was called once per question
    assert judge.generate_answer.call_count == 3
    assert judge.judge_correctness.call_count == 3
    # Generated answers reach individual_results
    answers = sorted(r.generated_answer for r in result.individual_results)
    assert answers == ["answer for A", "answer for B", "answer for C"]


@pytest.mark.asyncio
async def test_convomem_bench_reports_qa_metric_config() -> None:
    settings = EvalSettings(search_top_k=10, concurrency=1)
    bench = ConvoMemBenchmark(settings)
    client = AsyncMock()
    client.search = AsyncMock(return_value=_mock_search([]))
    judge = AsyncMock()
    judge.generate_answer = AsyncMock(return_value="x")
    judge.judge_correctness = AsyncMock(return_value=(True, 1.0))

    result = await bench.run(client, [_scenario("user_evidence", ["x"])], judge)
    assert result.config["metric"] == "end_to_end_qa_llm_judge"
    assert result.config["judge_used"] is True
    assert result.config["mode"] == "raw_per_message"
    # avg_evidence_recall is no longer reported — substring metric retired
    assert "avg_evidence_recall" not in result.retrieval_metrics
    assert "avg_judge_confidence" in result.retrieval_metrics
