"""Unit tests for the MemBench adapter and benchmark.

Adapter tests synthesize the topic-keyed file schema; benchmark tests
mock ``HebbClient.search`` so no real server is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from eval.benchmarks.membench_bench import MemBenchBenchmark
from eval.config import EvalSettings
from eval.datasets.base import EvalQuestion, EvalScenario
from eval.datasets.membench import MemBenchAdapter


# ---------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------


def _write_membench_fixture(tmp_path: Path) -> Path:
    """Two items under the ``noisy`` category, topic-keyed by 'movie'."""
    items: list[dict] = [
        {
            "_category_key": "noisy",
            "_topic_key": "movie",
            "tid": 100,
            "message_list": [
                # Per-session shape: list of sessions, one session here
                [
                    {"user": "Talked about Inception", "assistant": "Loved it",
                     "time": "2023-01-01", "sid": 0},
                    {"user": "Hated Tenet though", "assistant": "Same",
                     "time": "2023-01-02", "sid": 1},
                ],
            ],
            "QA": {
                "question": "Which movie did the user love?",
                "answer": "Inception",
                "choices": {"A": "Inception", "B": "Tenet"},
                "ground_truth": "A",
                "target_step_id": [[0, 0]],  # sid=0 → first turn
            },
        },
        {
            "_category_key": "noisy",
            "_topic_key": "movie",
            "tid": 101,
            "message_list": [
                # Flat shape: list of turns directly
                {"user": "Saw Dune yesterday", "assistant": "Good", "sid": 5},
                {"user": "Skipped Barbie", "assistant": "OK", "sid": 6},
            ],
            "QA": {
                "question": "Which movie did the user skip?",
                "answer": "Barbie",
                "choices": {"A": "Dune", "B": "Barbie"},
                "ground_truth": "B",
                "target_step_id": [[6]],
            },
        },
    ]
    fpath = tmp_path / "membench.json"
    fpath.write_text(json.dumps(items))
    return fpath


def test_membench_adapter_handles_both_message_list_shapes(tmp_path: Path) -> None:
    fpath = _write_membench_fixture(tmp_path)
    adapter = MemBenchAdapter(categories=("noisy",), topic="movie")
    scenarios = adapter.load(fpath)
    assert len(scenarios) == 2

    # Item 1: per-session shape, 2 turns
    s1 = scenarios[0]
    assert len(s1.conversations) == 2
    t = s1.conversations[0]
    assert "[User] Talked about Inception" in t.content
    assert "[Assistant] Loved it" in t.content
    assert t.metadata["sid"] == 0
    assert t.metadata["global_idx"] == 0
    assert t.metadata["s_idx"] == 0
    assert t.timestamp == "2023-01-01"

    q1 = s1.questions[0]
    assert q1.category == "noisy"
    assert q1.metadata["target_step_ids"] == [0]
    assert q1.metadata["topic"] == "movie"
    assert q1.metadata["tid"] == 100

    # Item 2: flat shape, sid=5 and 6 preserved
    s2 = scenarios[1]
    assert len(s2.conversations) == 2
    assert [t.metadata["sid"] for t in s2.conversations] == [5, 6]
    assert s2.questions[0].metadata["target_step_ids"] == [6]


def test_membench_adapter_skips_items_without_targets_or_question(tmp_path: Path) -> None:
    items = [
        {
            "_category_key": "noisy", "_topic_key": "movie", "tid": 1,
            "message_list": [{"user": "x", "assistant": "y"}],
            "QA": {"question": "?", "target_step_id": []},  # no targets
        },
        {
            "_category_key": "noisy", "_topic_key": "movie", "tid": 2,
            "message_list": [{"user": "x", "assistant": "y"}],
            "QA": {"question": "", "target_step_id": [[0]]},  # empty question
        },
    ]
    fpath = tmp_path / "m.json"
    fpath.write_text(json.dumps(items))
    assert MemBenchAdapter(categories=("noisy",)).load(fpath) == []


def test_membench_adapter_rejects_unknown_category() -> None:
    with pytest.raises(ValueError):
        MemBenchAdapter(categories=("not-a-real-cat",))


# ---------------------------------------------------------------------
# Benchmark — Hit@k scoring
# ---------------------------------------------------------------------


def _scenario(targets: list[int], category: str = "noisy") -> EvalScenario:
    sid = f"membench_{category}_movie_99"
    return EvalScenario(
        scenario_id=sid,
        conversations=[],
        questions=[EvalQuestion(
            question_id=f"{sid}_q",
            question="?",
            ground_truth="",
            category=category,
            evidence=[str(t) for t in targets],
            metadata={"target_step_ids": targets, "category": category, "topic": "movie"},
        )],
    )


def _mock_search(sids_in_order: list[int], scenario_id: str) -> dict:
    """Return memories with both sid and global_idx set to the same value
    so per-test we don't have to spell out both keys separately."""
    return {
        "results": [
            {
                "memory": {
                    "content": f"turn {sid}",
                    "metadata": {
                        "scenario_id": scenario_id,
                        "sid": sid,
                        "global_idx": sid,
                    },
                },
                "relevance_score": 1.0 - (i * 0.05),
            }
            for i, sid in enumerate(sids_in_order)
        ],
    }


@pytest.mark.asyncio
async def test_membench_bench_hit_at_5_when_target_in_topk() -> None:
    scenarios = [_scenario(targets=[3])]
    settings = EvalSettings(search_top_k=5, concurrency=1)
    bench = MemBenchBenchmark(settings)

    client = AsyncMock()
    # Target sid=3 at rank 2 (top-5)
    client.search = AsyncMock(
        return_value=_mock_search([10, 11, 3, 12, 13], scenarios[0].scenario_id)
    )
    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    assert result.correct == 1
    assert result.retrieval_metrics["hit@5"] == 1.0
    assert result.retrieval_metrics["hit@1"] == 0.0
    assert result.retrieval_metrics["hit@3"] == 1.0


@pytest.mark.asyncio
async def test_membench_bench_miss_when_target_absent() -> None:
    scenarios = [_scenario(targets=[99])]
    settings = EvalSettings(search_top_k=5, concurrency=1)
    bench = MemBenchBenchmark(settings)

    client = AsyncMock()
    client.search = AsyncMock(
        return_value=_mock_search([1, 2, 3, 4, 5], scenarios[0].scenario_id)
    )
    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    assert result.correct == 0
    assert result.retrieval_metrics["hit@5"] == 0.0


@pytest.mark.asyncio
async def test_membench_bench_matches_global_idx_when_sid_missing() -> None:
    """If a memory has global_idx but not sid, the match still works via global_idx."""
    scenarios = [_scenario(targets=[7])]
    settings = EvalSettings(search_top_k=5, concurrency=1)
    bench = MemBenchBenchmark(settings)

    sid = scenarios[0].scenario_id
    client = AsyncMock()
    # Only global_idx, no sid key
    client.search = AsyncMock(return_value={
        "results": [
            {
                "memory": {
                    "content": "turn",
                    "metadata": {"scenario_id": sid, "global_idx": 7},
                },
                "relevance_score": 0.9,
            }
        ],
    })
    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    assert result.correct == 1


@pytest.mark.asyncio
async def test_membench_bench_passes_partition_filter_to_search() -> None:
    """Cross-scenario isolation is enforced via partition_ids, not metadata.

    Each scenario lands in its own partition at setup time; search must
    pass ``partition_ids=[scenario_id]`` so the server returns only
    that item's haystack. This test verifies the bench actually does
    that — without it, top-k collapses under cross-scenario noise.
    """
    scenarios = [_scenario(targets=[3])]
    settings = EvalSettings(search_top_k=5, concurrency=1)
    bench = MemBenchBenchmark(settings)

    client = AsyncMock()
    client.search = AsyncMock(
        return_value=_mock_search([3], scenarios[0].scenario_id)
    )
    await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]

    # Inspect the call: must have included partition_ids=[scenario_id]
    kwargs = client.search.call_args.kwargs
    assert kwargs.get("partition_ids") == [scenarios[0].scenario_id]


@pytest.mark.asyncio
async def test_membench_bench_per_category_breakdown() -> None:
    s_noisy = _scenario(targets=[1], category="noisy")
    s_simple = _scenario(targets=[2], category="simple")
    scenarios = [s_noisy, s_simple]
    settings = EvalSettings(search_top_k=5, concurrency=1)
    bench = MemBenchBenchmark(settings)

    client = AsyncMock()
    client.search = AsyncMock(side_effect=[
        _mock_search([1], s_noisy.scenario_id),    # noisy hits
        _mock_search([99], s_simple.scenario_id),  # simple misses
    ])
    result = await bench.run(client, scenarios, judge=None)  # type: ignore[arg-type]
    assert result.accuracy_by_category["noisy"] == 1.0
    assert result.accuracy_by_category["simple"] == 0.0
