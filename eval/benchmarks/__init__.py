"""Benchmark runners for evaluation."""

from eval.benchmarks.convomem_bench import ConvoMemBenchmark
from eval.benchmarks.locomo_bench import LoComoBenchmark
from eval.benchmarks.locomo_qa_bench import LoComoQABenchmark
from eval.benchmarks.longmemeval_bench import (
    LongMemEvalBenchmark,
    LongMemEvalSessionDocBenchmark,
)
from eval.benchmarks.membench_bench import MemBenchBenchmark
from eval.benchmarks.memoryarena_bench import MemoryArenaBenchmark
from eval.benchmarks.personamem_bench import PersonaMemBenchmark

BENCHMARKS: dict[str, type] = {
    "locomo": LoComoBenchmark,
    "locomo-qa": LoComoQABenchmark,
    "longmemeval": LongMemEvalBenchmark,
    "longmemeval-session": LongMemEvalSessionDocBenchmark,
    "convomem": ConvoMemBenchmark,
    "membench": MemBenchBenchmark,
    "personamem": PersonaMemBenchmark,
    "memoryarena": MemoryArenaBenchmark,
}

__all__ = [
    "BENCHMARKS",
    "ConvoMemBenchmark",
    "LoComoBenchmark",
    "LoComoQABenchmark",
    "LongMemEvalBenchmark",
    "LongMemEvalSessionDocBenchmark",
    "MemBenchBenchmark",
    "MemoryArenaBenchmark",
    "PersonaMemBenchmark",
]
