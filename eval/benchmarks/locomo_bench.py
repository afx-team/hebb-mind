"""LoCoMo benchmark runner."""

from __future__ import annotations

from eval.benchmarks.base import BaseBenchmark


class LoComoBenchmark(BaseBenchmark):
    """Benchmark runner for the LoCoMo dataset."""

    benchmark_name = "locomo"
    dataset_name = "LoCoMo"
