"""Base types and protocol for dataset adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ConversationTurn:
    """A single dialogue turn."""

    role: str  # "user" or "assistant"
    content: str
    session_id: str | None = None
    turn_index: int = 0
    timestamp: str | None = None
    # Free-form per-turn metadata. MemBench uses it to carry the
    # dataset's local ``sid`` (turn id) so Hit@k can match a
    # ``target_step_id`` against retrieved memory metadata.
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalQuestion:
    """A question to evaluate against the memory system."""

    question_id: str
    question: str
    ground_truth: str
    category: str = "general"
    evidence: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalScenario:
    """A complete scenario: conversation history + questions."""

    scenario_id: str
    conversations: list[ConversationTurn]
    questions: list[EvalQuestion]
    metadata_extra: dict = field(default_factory=dict)


class DatasetAdapter(Protocol):
    """Protocol for loading and normalizing benchmark datasets."""

    @property
    def name(self) -> str: ...

    async def download(self, data_dir: Path) -> Path:
        """Download dataset to data_dir. Return path to downloaded data."""
        ...

    def load(self, data_path: Path) -> list[EvalScenario]:
        """Parse downloaded data into normalized EvalScenarios."""
        ...
