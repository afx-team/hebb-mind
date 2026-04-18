"""LongMemEval benchmark runner."""

from __future__ import annotations

from eval.benchmarks.base import BaseBenchmark


class LongMemEvalBenchmark(BaseBenchmark):
    """Benchmark runner for the LongMemEval dataset."""

    benchmark_name = "longmemeval"
    dataset_name = "LongMemEval"
