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
async def test_convomem_bench_per_category_aggregation() -> None:
    scenarios = [
        _scenario("user_evidence", ["fact A"]),
        _scenario("user_evidence", ["fact B"]),
        _scenario("preference_evidence", ["fact C"]),
    ]
    settings = EvalSettings(search_top_k=5, concurrency=1)
    bench = ConvoMemBenchmark(settings)

    client = AsyncMock()

    # First two questions: 'fact A' is retrieved, 'fact B' isn't, 'fact C' is.
    responses = [
        _mock_search(["I know fact A clearly"]),
        _mock_search(["unrelated content"]),
        _mock_search(["fact C is here"]),
    ]
    client.search = AsyncMock(side_effect=responses)

    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]

    assert result.total_questions == 3
    assert result.correct == 2
    # 1 of 2 user_evidence perfect, full preference_evidence perfect
    assert result.accuracy_by_category["user_evidence"] == 0.5
    assert result.accuracy_by_category["preference_evidence"] == 1.0
    # Mean recall = (1 + 0 + 1) / 3
    assert pytest.approx(result.retrieval_metrics["avg_evidence_recall"], rel=1e-3) == 2 / 3
    assert result.retrieval_metrics["zero_recall_rate"] == pytest.approx(1 / 3, rel=1e-3)


@pytest.mark.asyncio
async def test_convomem_bench_reports_metric_config() -> None:
    settings = EvalSettings(search_top_k=10, concurrency=1)
    bench = ConvoMemBenchmark(settings)
    client = AsyncMock()
    client.search = AsyncMock(return_value=_mock_search([]))

    result = await bench.run(client, [_scenario("user_evidence", ["x"])], judge=None)  # type: ignore[arg-type]
    assert result.config["metric"] == "substring_evidence_recall"
    assert result.config["mode"] == "raw_per_message"
