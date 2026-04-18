"""ConvoMem benchmark runner."""

from __future__ import annotations

from eval.benchmarks.base import BaseBenchmark


class ConvoMemBenchmark(BaseBenchmark):
    """Benchmark runner for the ConvoMem dataset."""

    benchmark_name = "convomem"
    dataset_name = "ConvoMem"

    def _format_turn(self, turn) -> str:
        return f"[Turn {turn.turn_index}] {turn.role}: {turn.content}"
