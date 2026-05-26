"""Benchmark runners for evaluation."""

from eval.benchmarks.convomem_bench import ConvoMemBenchmark
from eval.benchmarks.locomo_bench import LoComoBenchmark
from eval.benchmarks.longmemeval_bench import LongMemEvalBenchmark
from eval.benchmarks.membench_bench import MemBenchBenchmark
from eval.benchmarks.memoryarena_bench import MemoryArenaBenchmark
from eval.benchmarks.personamem_bench import PersonaMemBenchmark

BENCHMARKS: dict[str, type] = {
    "locomo": LoComoBenchmark,
    "longmemeval": LongMemEvalBenchmark,
    "convomem": ConvoMemBenchmark,
    "membench": MemBenchBenchmark,
    "personamem": PersonaMemBenchmark,
    "memoryarena": MemoryArenaBenchmark,
}

__all__ = [
    "BENCHMARKS",
    "ConvoMemBenchmark",
    "LoComoBenchmark",
    "LongMemEvalBenchmark",
    "MemBenchBenchmark",
    "MemoryArenaBenchmark",
    "PersonaMemBenchmark",
]
