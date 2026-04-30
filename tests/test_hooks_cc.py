"""Tests for Claude Code integration hooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from hippocampus.ingest.noise import strip_noise
from hippocampus.integrations.claude_code import dedup, recall, stop, write


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


class TestStopHook:
    def test_triggers_consolidation_and_cleanup(self, monkeypatch: pytest.MonkeyPatch):
        client = _FakeClient()
        cleaned: list[str] = []
        monkeypatch.setattr(stop, "read_hook_input", lambda: {"session_id": "s1"})
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        monkeypatch.setattr(stop, "cleanup_session", lambda session_id: cleaned.append(session_id))
        stop.handle()
        assert client.calls == [("/api/v1/admin/consolidate", None)]
        assert cleaned == ["s1"]
        assert client.closed is True
