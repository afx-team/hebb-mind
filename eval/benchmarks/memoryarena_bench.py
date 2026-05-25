"""MemoryArena benchmark runner (stub)."""

from __future__ import annotations

from eval.benchmarks.base import BenchmarkResult
from eval.client import HebbClient
from eval.config import EvalSettings
from eval.datasets.base import EvalScenario
from eval.judge import LLMJudge


class MemoryArenaBenchmark:
    """Stub runner for the MemoryArena benchmark."""

    def __init__(self, settings: EvalSettings):
        self.settings = settings

    @property
    def name(self) -> str:
        return "memoryarena"

    async def setup(
        self, client: HebbClient, scenarios: list[EvalScenario]
    ) -> None:
        raise NotImplementedError("MemoryArena benchmark is not yet implemented.")

    async def run(
        self,
        client: HebbClient,
        scenarios: list[EvalScenario],
        judge: LLMJudge,
    ) -> BenchmarkResult:
        raise NotImplementedError("MemoryArena benchmark is not yet implemented.")

    async def teardown(self, client: HebbClient) -> None:
        pass
