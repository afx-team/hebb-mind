"""PersonaMem benchmark runner."""

from __future__ import annotations

from eval.benchmarks.base import BaseBenchmark


class PersonaMemBenchmark(BaseBenchmark):
    """Benchmark runner for the PersonaMem dataset."""

    benchmark_name = "personamem"
    dataset_name = "PersonaMem"

    def _format_turn(self, turn) -> str:
        return f"[Turn {turn.turn_index}] {turn.role}: {turn.content}"
