"""Tests for Claude Code integration hooks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hippocampus.ingest.noise import strip_noise
from hippocampus.integrations.claude_code import dedup, install, recall, stop, write
from hippocampus.integrations.claude_code.transcript import (
    TurnSummary,
    extract_last_turn,
    format_turn_memory,
)


class _FakeResponse:
    def __init__(self, payload: dict | None = None) -> None:
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {}
        self.calls: list[tuple[str, dict | None]] = []
        self.closed = False

    def post(self, path: str, json: dict | None = None) -> _FakeResponse:
        self.calls.append((path, json))
        return _FakeResponse(self.payload)

    def close(self) -> None:
        self.closed = True


class TestStripNoise:
    def test_removes_system_reminder_block(self):
        raw = "<system-reminder>hidden context</system-reminder>Remember I like salmon"
        assert strip_noise(raw) == "Remember I like salmon"

    def test_removes_local_command_stdout_block(self):
        raw = "<local-command-stdout>debug output</local-command-stdout>Actual content"
        assert strip_noise(raw) == "Actual content"

    def test_removes_command_name_tag(self):
        raw = "<command-name>/mcp</command-name>Tell me about memory"
        assert strip_noise(raw) == "Tell me about memory"


class TestDedup:
    def test_content_hash_is_stable(self):
        assert dedup.content_hash(" I like Salmon ") == dedup.content_hash("i like salmon")

    def test_is_duplicate_scoped_per_session(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(dedup, "STATE_DIR", tmp_path)
        monkeypatch.setattr(dedup, "STATE_FILE", tmp_path / "hook_state.json")

        assert dedup.is_duplicate("s1", "I like salmon") is False


class TestInstallHook:
    def test_installs_mcp_with_claude_cli_when_available(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        calls: list[list[str]] = []
        settings_path = tmp_path / "settings.json"

        def fake_which(name: str) -> str | None:
            return f"/bin/{name}"

        def fake_run(args: list[str], **kwargs):
            calls.append(args)

            class Result:
                returncode = 0

            return Result()

        monkeypatch.setattr(install.shutil, "which", fake_which)
        monkeypatch.setattr(install.subprocess, "run", fake_run)
        monkeypatch.setattr(install, "_find_settings_path", lambda scope: settings_path)

        install.handle("user")

        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        assert "mcpServers" not in data
        assert calls == [
            [
                "claude",
                "mcp",
                "add",
                "--transport",
                "stdio",
                "--scope",
                "user",
                "hippocampus",
                "--",
                "hippocampus-mcp",
            ]
        ]

    def test_installs_mcp_in_settings_when_claude_cli_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        settings_path = tmp_path / "settings.json"

        def fake_which(name: str) -> str | None:
            if name == "claude":
                return None
            return f"/bin/{name}"

        monkeypatch.setattr(install.shutil, "which", fake_which)
        monkeypatch.setattr(install, "_find_settings_path", lambda scope: settings_path)

        install.handle("user")

        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        assert data["mcpServers"]["hippocampus"]["command"] == "hippocampus-mcp"
        dedup.record_written("s1", "I like salmon")
        assert dedup.is_duplicate("s1", "I like salmon") is True
        assert dedup.is_duplicate("s2", "I like salmon") is False

    def test_cleanup_session_removes_state(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(dedup, "STATE_DIR", tmp_path)
        monkeypatch.setattr(dedup, "STATE_FILE", tmp_path / "hook_state.json")

        dedup.record_written("s1", "I like salmon")
        assert dedup.is_duplicate("s1", "I like salmon") is True
        dedup.cleanup_session("s1")
        assert dedup.is_duplicate("s1", "I like salmon") is False


class TestWriteHook:
    def test_skips_trivial_prompt(self, monkeypatch: pytest.MonkeyPatch):
        calls: list[str] = []
        monkeypatch.setattr(write, "read_hook_input", lambda: {"session_id": "s1", "prompt": "ok"})
        monkeypatch.setattr(write, "get_client", lambda timeout=8: calls.append("client"))
        write.handle()
        assert calls == []

    def test_skips_duplicate_prompt(self, monkeypatch: pytest.MonkeyPatch):
        calls: list[str] = []
        monkeypatch.setattr(
            write, "read_hook_input", lambda: {"session_id": "s1", "prompt": "Remember I like salmon a lot"}
        )
        monkeypatch.setattr(write, "is_duplicate", lambda session_id, text: True)
        monkeypatch.setattr(write, "get_client", lambda timeout=8: calls.append("client"))
        write.handle()
        assert calls == []

    def test_writes_cleaned_prompt(self, monkeypatch: pytest.MonkeyPatch):
        client = _FakeClient()
        recorded: list[tuple[str, str]] = []
        monkeypatch.setattr(
            write,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "prompt": "<system-reminder>hidden</system-reminder>Remember that I like salmon for dinner",
            },
        )
        monkeypatch.setattr(write, "get_client", lambda timeout=8: client)
        monkeypatch.setattr(write, "is_duplicate", lambda session_id, text: False)
        monkeypatch.setattr(write, "record_written", lambda session_id, text: recorded.append((session_id, text)))
        write.handle()
        assert client.calls == [
            (
                "/api/v1/memories",
                {
                    "content": "Remember that I like salmon for dinner",
                    "partition_id": "mem_hippocampus",
                    "importance_score": 5.0,
                    "tags": ["user-prompt", "hook"],
                    "metadata": {"session_id": "s1"},
                    "source": "hook",
                },
            )
        ]
        assert recorded == [("s1", "Remember that I like salmon for dinner")]
        assert client.closed is True


class TestRecallHook:
    def test_filters_current_session_keeps_other_inbox(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        client = _FakeClient(
            {
                "results": [
                    {
                        "score": 0.9,
                        "memory": {
                            "partition_id": "semantic",
                            "content": "Current session memory",
                            "tags": [],
                            "metadata": {"session_id": "s1"},
                        },
                    },
                    {
                        "score": 0.85,
                        "memory": {
                            "partition_id": "mem_hippocampus",
                            "content": "Other session working memory",
                            "tags": ["hook"],
                            "metadata": {"session_id": "old"},
                        },
                    },
                    {
                        "score": 0.8,
                        "memory": {
                            "partition_id": "preference",
                            "content": "User likes salmon",
                            "tags": ["food"],
                            "metadata": {"session_id": "old"},
                        },
                    },
                ]
            }
        )
        monkeypatch.setattr(recall, "read_hook_input", lambda: {"session_id": "s1"})
        monkeypatch.setattr(recall, "get_client", lambda timeout=20: client)
        recall.handle()
        output = capsys.readouterr().out
        assert "Current session memory" not in output
        assert "Other session working memory" in output
        assert "User likes salmon" in output
        assert "<cross-session-memory" in output
        assert client.closed is True

    def test_silent_when_no_results(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        client = _FakeClient({"results": []})
        monkeypatch.setattr(recall, "read_hook_input", lambda: {"session_id": "s1"})
        monkeypatch.setattr(recall, "get_client", lambda timeout=20: client)
        recall.handle()
        assert capsys.readouterr().out == ""


class TestTranscript:
    """Tests for transcript parsing and turn summary formatting."""

    def _write_jsonl(self, tmp_path: Path, messages: list[dict]) -> Path:
        """Helper to write a JSONL transcript file."""
        path = tmp_path / "session.jsonl"
        with open(path, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")
        return path

    def test_extract_user_and_assistant_text(self, tmp_path: Path):
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "What is 1+1?"}]},
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "The answer is 2."}]},
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.user_input == "What is 1+1?"
        assert summary.assistant_output == "The answer is 2."
        assert summary.tools == []
        assert summary.mcps == []

    def test_extract_tools_and_mcps(self, tmp_path: Path):
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Read the file"}]},
                },
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Let me read that."},
                            {"type": "tool_use", "name": "Read", "id": "t1", "input": {}},
                            {"type": "tool_use", "name": "Grep", "id": "t2", "input": {}},
                            {"type": "tool_use", "name": "mcp__hippocampus__search_memory", "id": "t3", "input": {}},
                        ],
                    },
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.tools == ["Read", "Grep"]
        assert summary.mcps == ["mcp__hippocampus__search_memory"]

    def test_deduplicates_repeated_tools(self, tmp_path: Path):
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Search for it"}]},
                },
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Grep", "id": "t1", "input": {}},
                            {"type": "tool_use", "name": "Grep", "id": "t2", "input": {}},
                            {"type": "tool_use", "name": "Read", "id": "t3", "input": {}},
                        ],
                    },
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.tools == ["Grep", "Read"]

    def test_strips_system_noise_from_user_input(self, tmp_path: Path):
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "<system-reminder>hidden</system-reminder>Actual question here"},
                        ],
                    },
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "Sure!"}]},
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.user_input == "Actual question here"

    def test_extracts_last_turn_only(self, tmp_path: Path):
        """When there are multiple turns, only the last one is extracted."""
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "First question"}]},
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "First answer"}]},
                },
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Second question"}]},
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "Second answer"}]},
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.user_input == "Second question"
        assert summary.assistant_output == "Second answer"

    def test_returns_none_for_missing_file(self):
        summary = extract_last_turn("/nonexistent/path.jsonl")
        assert summary is None

    def test_returns_none_for_empty_file(self, tmp_path: Path):
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        assert extract_last_turn(path) is None

    def test_collects_tools_from_multiple_assistant_messages(self, tmp_path: Path):
        """Tools from all assistant messages in the last turn are collected."""
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Do stuff"}]},
                },
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "name": "Read", "id": "t1", "input": {}}],
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Done."},
                            {"type": "tool_use", "name": "Edit", "id": "t2", "input": {}},
                        ],
                    },
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.tools == ["Edit", "Read"]
        assert summary.assistant_output == "Done."


class TestFormatTurnMemory:
    def test_formats_full_summary(self):
        summary = TurnSummary(
            user_input="What is 1+1?",
            assistant_output="The answer is 2.",
            tools=["Read", "Grep"],
            mcps=["mcp__hippocampus__search_memory"],
        )
        result = format_turn_memory(summary)
        assert "[User] What is 1+1?" in result
        assert "[Assistant] The answer is 2." in result
        assert "[Tools] Read, Grep" in result
        assert "[MCP] mcp__hippocampus__search_memory" in result

    def test_skips_empty_sections(self):
        summary = TurnSummary(user_input="Hello", assistant_output="Hi")
        result = format_turn_memory(summary)
        assert "[Tools]" not in result
        assert "[MCP]" not in result


class TestStopHook:
    def test_cleanup_without_transcript(self, monkeypatch: pytest.MonkeyPatch):
        """No transcript_path → only dedup cleanup, no client needed."""
        cleaned: list[str] = []
        monkeypatch.setattr(stop, "read_hook_input", lambda: {"session_id": "s1"})
        monkeypatch.setattr(stop, "cleanup_session", lambda session_id: cleaned.append(session_id))
        stop.handle()
        assert cleaned == ["s1"]

    def test_records_turn_summary_from_transcript(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Explain this code"}]},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "This function does X."},
                            {"type": "tool_use", "name": "Read", "id": "t1", "input": {}},
                        ],
                    },
                }
            )
            + "\n"
        )

        client = _FakeClient()
        cleaned: list[str] = []
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {"session_id": "s1", "transcript_path": str(transcript)},
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        monkeypatch.setattr(stop, "cleanup_session", lambda session_id: cleaned.append(session_id))

        stop.handle()

        # Only turn summary write, no consolidation
        assert len(client.calls) == 1
        path, payload = client.calls[0]
        assert path == "/api/v1/memories"
        assert "[User] Explain this code" in payload["content"]
        assert "[Assistant] This function does X." in payload["content"]
        assert "[Tools] Read" in payload["content"]
        assert payload["tags"] == ["turn-summary", "hook"]
        assert payload["metadata"]["tools"] == ["Read"]
        assert payload["source"] == "hook:stop"
        assert client.closed is True
        assert cleaned == ["s1"]
