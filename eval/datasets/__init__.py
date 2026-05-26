"""Dataset adapters for evaluation benchmarks."""

from eval.datasets.convomem import ConvoMemAdapter
from eval.datasets.locomo import LoCoMoAdapter
from eval.datasets.longmemeval import LongMemEvalAdapter
from eval.datasets.membench import MemBenchAdapter
from eval.datasets.memoryarena import MemoryArenaAdapter
from eval.datasets.personamem import PersonaMemAdapter

ADAPTERS: dict[str, type] = {
    "locomo": LoCoMoAdapter,
    "longmemeval": LongMemEvalAdapter,
    "convomem": ConvoMemAdapter,
    "membench": MemBenchAdapter,
    "personamem": PersonaMemAdapter,
    "memoryarena": MemoryArenaAdapter,
}

__all__ = [
    "ADAPTERS",
    "ConvoMemAdapter",
    "LoCoMoAdapter",
    "LongMemEvalAdapter",
    "MemBenchAdapter",
    "MemoryArenaAdapter",
    "PersonaMemAdapter",
]
