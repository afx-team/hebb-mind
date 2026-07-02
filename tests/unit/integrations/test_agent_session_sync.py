"""Tests for local Codex / Claude Code session collection."""

from __future__ import annotations

import json
from pathlib import Path

from hebb.integrations import session_sync


def _codex_message(role: str, text: str) -> str:
    block_type = "output_text" if role == "assistant" else "input_text"
    return json.dumps(
        {
            "timestamp": "2026-06-30T01:02:03.000Z",
            "type": "response_item",
            "payload": {"type": "message", "role": role, "content": [{"type": block_type, "text": text}]},
        }
    )


def _claude_line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)


def test_discovers_codex_sessions_and_skips_setup_context(tmp_path: Path, monkeypatch) -> None:
    codex_home = tmp_path / "codex"
    archived = codex_home / "archived_sessions"
    archived.mkdir(parents=True)
    transcript = archived / "rollout-2026-06-30T01-02-03-session-a.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-06-30T01:00:00.000Z",
                        "type": "session_meta",
                        "payload": {"id": "session-a", "cwd": str(tmp_path / "repo")},
                    }
                ),
                _codex_message("user", "# AGENTS.md instructions for /tmp/repo\n\n<INSTRUCTIONS>...</INSTRUCTIONS>"),
                _codex_message("user", "<environment_context>\n  <cwd>/tmp/repo</cwd>\n</environment_context>"),
                _codex_message("user", "Remember that this project uses pnpm."),
                json.dumps(
                    {
                        "timestamp": "2026-06-30T01:02:04.000Z",
                        "type": "response_item",
                        "payload": {"type": "function_call", "name": "exec_command", "arguments": "{}"},
                    }
                ),
                _codex_message("assistant", "Recorded."),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "empty-claude"))

    sessions = session_sync.discover_sessions(host="codex")

    assert len(sessions) == 1
    session = sessions[0]
    assert session.host == "codex"
    assert session.session_id == "session-a"
    assert session.turn_count == 1
    assert session.turns[0].turn == 2
    assert "Remember that this project uses pnpm." in session.turns[0].content


def test_discovers_claude_code_sessions(tmp_path: Path, monkeypatch) -> None:
    claude_home = tmp_path / "claude"
    project = claude_home / "projects" / "-tmp-repo"
    project.mkdir(parents=True)
    transcript = project / "session-b.jsonl"
    transcript.write_text(
        "\n".join(
            [
                _claude_line({"type": "mode", "mode": "normal", "sessionId": "session-b"}),
                _claude_line(
                    {
                        "type": "user",
                        "timestamp": "2026-06-30T02:00:00.000Z",
                        "sessionId": "session-b",
                        "cwd": str(tmp_path / "repo"),
                        "message": {"role": "user", "content": [{"type": "text", "text": "Explain the sync design."}]},
                    }
                ),
                _claude_line(
                    {
                        "type": "assistant",
                        "timestamp": "2026-06-30T02:00:03.000Z",
                        "sessionId": "session-b",
                        "cwd": str(tmp_path / "repo"),
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "Use hooks and a batch importer."},
                                {"type": "tool_use", "name": "Read", "id": "tool-1", "input": {}},
                            ],
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty-codex"))

    sessions = session_sync.discover_sessions(host="claude_code")

    assert len(sessions) == 1
    assert sessions[0].session_id == "session-b"
    assert sessions[0].turns[0].tools == ["Read"]
    assert "Use hooks and a batch importer." in sessions[0].turns[0].content


def test_memory_create_stamps_sync_metadata(tmp_path: Path) -> None:
    session = session_sync.AgentSession(
        id="abc",
        host="codex",
        path=str(tmp_path / "rollout.jsonl"),
        session_id="session-a",
        project="repo",
        updated_at=1.0,
        turns=[
            session_sync.AgentTurn(
                session_id="session-a",
                turn=3,
                content="[User] Remember this.",
                timestamp="2026-06-30T01:02:03.000Z",
                tools=["exec_command"],
                mcps=[],
            )
        ],
    )

    memory = session_sync.to_memory_create(session, session.turns[0])
    meta = memory.metadata.model_dump()

    assert memory.partition_id == "mem_hippocampus"
    assert memory.source == "sync:codex"
    assert memory.tags == ["repo"]
    assert meta["host"] == "codex"
    assert meta["session_id"] == "session-a"
    assert meta["turn"] == 3
    assert meta["source_path"] == str(tmp_path / "rollout.jsonl")
