"""Tests for agent session sync API behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hebb.models.memory import Memory, MemoryCreate
from hebb.server.routers.agent_sync import AgentSyncRequest, list_sessions, sync_sessions


class _Store:
    def __init__(self) -> None:
        self.memories: list[Memory] = []

    async def get_by_partition(self, partition_id: str) -> list[Memory]:
        return [memory for memory in self.memories if memory.partition_id == partition_id]

    async def create(self, data: MemoryCreate, embedding: list[float] | None = None) -> Memory:
        memory = Memory(**data.model_dump())
        self.memories.append(memory)
        return memory


class _Embedder:
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def _codex_message(role: str, text: str) -> str:
    block_type = "output_text" if role == "assistant" else "input_text"
    return json.dumps(
        {
            "timestamp": "2026-06-30T01:02:03.000Z",
            "type": "response_item",
            "payload": {"type": "message", "role": role, "content": [{"type": block_type, "text": text}]},
        }
    )


def _write_codex_session(home: Path) -> None:
    archived = home / "archived_sessions"
    archived.mkdir(parents=True)
    (archived / "rollout-2026-06-30T01-02-03-session-a.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-06-30T01:00:00.000Z",
                        "type": "session_meta",
                        "payload": {"id": "session-a", "cwd": "/tmp/repo"},
                    }
                ),
                _codex_message("user", "Remember the sync contract."),
                _codex_message("assistant", "Stored."),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_list_sessions_reports_unsynced_turns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / "codex"
    _write_codex_session(codex_home)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    store = _Store()

    sessions = await list_sessions(host="codex", limit=10, store=store)

    assert len(sessions) == 1
    assert sessions[0].turn_count == 1
    assert sessions[0].synced_turns == 0
    assert sessions[0].unsynced_turns == 1


@pytest.mark.asyncio
async def test_sync_sessions_creates_then_deduplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / "codex"
    _write_codex_session(codex_home)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    store = _Store()
    embedder = _Embedder()

    first = await sync_sessions(AgentSyncRequest(host="codex"), store=store, embedder=embedder)
    second = await sync_sessions(AgentSyncRequest(host="codex"), store=store, embedder=embedder)

    assert first.memories_created == 1
    assert first.skipped_existing == 0
    assert len(store.memories) == 1
    assert store.memories[0].source == "sync:codex"
    assert store.memories[0].metadata.model_dump()["host"] == "codex"
    assert second.memories_created == 0
    assert second.skipped_existing == 1
    assert len(store.memories) == 1
