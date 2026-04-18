"""MemoryArena dataset adapter (stub).

MemoryArena tests multi-session agentic tasks with interdependent subtasks.
This adapter is a placeholder for future implementation.

Source: https://memoryarena.github.io/
"""

from __future__ import annotations

import logging
from pathlib import Path

from eval.datasets.base import EvalScenario

logger = logging.getLogger(__name__)


class MemoryArenaAdapter:
    """Stub adapter for the MemoryArena benchmark dataset."""

    @property
    def name(self) -> str:
        return "memoryarena"

    async def download(self, data_dir: Path) -> Path:
        raise NotImplementedError(
            "MemoryArena adapter is not yet implemented. "
            "The dataset uses a task-completion format that requires "
            "a different evaluation pipeline. Coming soon."
        )

    def load(self, data_path: Path) -> list[EvalScenario]:
        raise NotImplementedError("MemoryArena adapter is not yet implemented.")
