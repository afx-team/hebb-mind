"""Dataset adapters for evaluation benchmarks."""

from eval.datasets.convomem import ConvoMemAdapter
from eval.datasets.locomo import LoCoMoAdapter
from eval.datasets.longmemeval import LongMemEvalAdapter
from eval.datasets.membench import MemBenchAdapter
from eval.datasets.memoryarena import MemoryArenaAdapter
from eval.datasets.personamem import PersonaMemAdapter

ADAPTERS: dict[str, type] = {
    "locomo": LoCoMoAdapter,
    # locomo-qa shares the LoCoMo dataset; the QA benchmark just runs a
    # different scorer over the same retrieval pipeline.
    "locomo-qa": LoCoMoAdapter,
    "longmemeval": LongMemEvalAdapter,
    # Session-doc variant reuses the same dataset; only the bench's
    # ingest strategy differs.
    "longmemeval-session": LongMemEvalAdapter,
    "convomem": ConvoMemAdapter,
    # MemPalace-aligned 5×50 substring slice — reuses the same dataset.
    "convomem-substring": ConvoMemAdapter,
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
