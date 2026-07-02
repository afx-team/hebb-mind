"""Tests for Claude Code integration hooks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hebb.ingest.noise import (
    clean_user_input,
    is_greeting_only,
    strip_base64_blobs,
    strip_code_fences,
    strip_html_tags,
    strip_noise,
)
from hebb.integrations.claude_code import _client, install, recall, stop
from hebb.integrations.claude_code.transcript import (
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


class TestStripCodeFences:
    def test_removes_multiline_fenced_block(self):
        raw = "Here is the bug:\n```python\nfor i in range(10):\n    print(i)\n```\nWhat went wrong?"
        assert strip_code_fences(raw) == "Here is the bug:\n\nWhat went wrong?"

    def test_removes_fence_without_language_hint(self):
        raw = "trace:\n```\nTraceback (most recent call last):\n  File ...\n```\nplease help"
        assert strip_code_fences(raw) == "trace:\n\nplease help"

    def test_removes_inline_triple_backtick_span(self):
        raw = "set ```DEBUG=true``` and retry"
        assert strip_code_fences(raw) == "set  and retry"

    def test_passthrough_when_no_fence(self):
        assert strip_code_fences("just plain prose, no fences.") == "just plain prose, no fences."

    def test_passthrough_empty(self):
        assert strip_code_fences("") == ""


class TestStripHtmlTags:
    def test_removes_paired_block_and_body(self):
        raw = "Before <div class='x'>inner <b>bold</b> text</div> after"
        assert strip_html_tags(raw) == "Before  after"

    def test_removes_standalone_tag(self):
        raw = "line one<br/>line two"
        assert strip_html_tags(raw) == "line oneline two"

    def test_leaves_chevron_prose_alone(self):
        raw = "if 3 < x < 5 then proceed"
        assert strip_html_tags(raw) == "if 3 < x < 5 then proceed"


class TestStripBase64Blobs:
    def test_removes_long_bare_base64(self):
        blob = "A" * 100
        raw = f"prefix {blob} suffix"
        assert strip_base64_blobs(raw) == "prefix  suffix"

    def test_removes_data_uri(self):
        raw = "see attached data:image/png;base64,iVBORw0KGgoAAAANSUhEUg== please"
        assert "iVBORw0KGgo" not in strip_base64_blobs(raw)

    def test_preserves_short_alphanumeric_tokens(self):
        raw = "token abc123XYZdef ok"
        assert strip_base64_blobs(raw) == "token abc123XYZdef ok"


class TestCleanUserInput:
    def test_composed_pipeline_strips_everything(self):
        raw = (
            "<system-reminder>secret</system-reminder>"
            "Please debug this:\n```python\nfor i in range(3): print(i)\n```\n"
            "Also rendered as <span>span text</span> and binary "
            + ("A" * 90)
            + " thanks!"
        )
        cleaned = clean_user_input(raw)
        assert "<system-reminder" not in cleaned
        assert "for i in range" not in cleaned
        assert "<span>" not in cleaned
        assert "A" * 90 not in cleaned
        assert "Please debug this" in cleaned


class TestIsGreetingOnly:
    @pytest.mark.parametrize(
        "msg",
        ["hi", "Hello", "thanks!", "thank you.", "你好", "好的", "嗯嗯", "晚安", "ok", "Got it"],
    )
    def test_recognises_pure_greeting(self, msg: str):
        assert is_greeting_only(msg) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "hi, can you help with X?",       # greeting + substantive ask
            "thanks for the explanation now do Y",
            "你好，我想问一下记忆系统怎么用",
            "ok let's move on to the next step",
            "",                                # empty
            "fix this bug",                    # plain ask
        ],
    )
    def test_rejects_non_pure_greeting(self, msg: str):
        assert is_greeting_only(msg) is False


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
        monkeypatch.chdir(tmp_path)

        install.handle("user")

        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        # Hooks must carry the absolute path to hebb, not the bare name.
        recall_cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert recall_cmd == "/bin/hebb claude-code recall"
        # MCP registered through `claude mcp add` — settings.json should not
        # also carry the server (so `claude mcp list` is the single source of
        # truth).
        assert "mcpServers" not in data
        # First call is the pre-remove (idempotent re-install); second is add.
        assert calls[0] == ["claude", "mcp", "remove", "hebb", "-s", "user"]
        assert calls[1] == [
            "claude",
            "mcp",
            "add",
            "--transport",
            "stdio",
            "--scope",
            "user",
            "hebb",
            "--",
            "/bin/hebb-mcp",
        ]

    def test_falls_back_to_python_m_when_hebb_not_on_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Critical: install must work even when `pip install --user` left
        `hebb` outside PATH — the hooks we write into settings.json have to
        run from inside a GUI app's subprocess, which can't see the shell PATH.
        """
        settings_path = tmp_path / "settings.json"

        # Nothing on PATH — no hebb, no hebb-mcp, no claude.
        monkeypatch.setattr(install.shutil, "which", lambda name: None)
        # Pin sys.executable to a known absolute path for deterministic asserts.
        monkeypatch.setattr("hebb.utils.cli_paths.sys.executable", "/opt/py/bin/python3")
        monkeypatch.setattr(install, "_find_settings_path", lambda scope: settings_path)
        monkeypatch.chdir(tmp_path)

        install.handle("user")

        data = json.loads(settings_path.read_text())
        recall_cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert recall_cmd == "/opt/py/bin/python3 -m hebb.cli.main claude-code recall"
        # Same for the MCP entry written to settings.json (claude CLI absent).
        mcp = data["mcpServers"]["hebb"]
        assert mcp["command"] == "/opt/py/bin/python3"
        assert mcp["args"] == ["-m", "hebb.mcp.server"]

    def test_reinstall_replaces_legacy_bare_hooks(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Running install twice must not stack duplicate hebb hooks, and
        must replace any legacy bare-name commands a previous version wrote.
        """
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "matcher": "",
                                "hooks": [
                                    {"type": "command", "command": "hebb cc recall", "timeout": 30},
                                    {"type": "command", "command": "unrelated-tool", "timeout": 5},
                                ],
                            }
                        ]
                    }
                }
            )
        )
        monkeypatch.setattr(install.shutil, "which", lambda name: f"/bin/{name}" if name != "claude" else None)
        monkeypatch.setattr(install, "_find_settings_path", lambda scope: settings_path)
        monkeypatch.chdir(tmp_path)

        install.handle("user")

        data = json.loads(settings_path.read_text())
        commands = [
            h["command"]
            for entry in data["hooks"]["SessionStart"]
            for h in entry["hooks"]
        ]
        # Legacy bare command (old `cc` name) is gone, replaced with the
        # absolute path using the current `claude-code` group name.
        assert "hebb cc recall" not in commands
        assert "/bin/hebb claude-code recall" in commands
        # Unrelated hooks survive.
        assert "unrelated-tool" in commands

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
        monkeypatch.chdir(tmp_path)

        install.handle("user")

        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        # When claude CLI is missing the absolute MCP path lands in settings.json.
        assert data["mcpServers"]["hebb"]["command"] == "/bin/hebb-mcp"


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


class TestResolveSessionId:
    def test_prefers_explicit_session_id(self):
        assert _client.resolve_session_id({"session_id": "abc", "transcript_path": "/x"}) == "abc"

    def test_derives_stable_hash_from_transcript_path(self):
        first = _client.resolve_session_id({"transcript_path": "/tmp/foo.jsonl"})
        second = _client.resolve_session_id({"transcript_path": "/tmp/foo.jsonl"})
        assert first == second
        assert len(first) == 16
        # Different transcript → different id.
        assert _client.resolve_session_id({"transcript_path": "/tmp/bar.jsonl"}) != first

    def test_returns_empty_when_neither_present(self):
        assert _client.resolve_session_id({}) == ""


class TestPromptRecallHook:
    def test_uses_user_prompt_as_query(self, monkeypatch: pytest.MonkeyPatch):
        client = _FakeClient({"results": []})
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"session_id": "s1", "prompt": "How do I reset my password?"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        assert client.calls == [
            (
                "/api/v1/search",
                {"query": "How do I reset my password?", "top_k": 20, "strict_recall": True},
            ),
        ]
        assert client.closed is True

    def test_strips_noise_from_prompt_before_querying(self, monkeypatch: pytest.MonkeyPatch):
        client = _FakeClient({"results": []})
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "prompt": "<system-reminder>x</system-reminder>What's the deploy flag?",
            },
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        assert client.calls[0][1]["query"] == "What's the deploy flag?"

    def test_skips_too_short_prompt(self, monkeypatch: pytest.MonkeyPatch):
        opened: list[str] = []
        monkeypatch.setattr(recall, "read_hook_input", lambda: {"session_id": "s1", "prompt": "hi"})
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: opened.append("client"))
        recall.handle_prompt()
        assert opened == []

    def test_filters_current_session_via_transcript_hash(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        # session_id is missing — handler must hash transcript_path and use
        # that derived id to filter current-session memories.
        derived = _client.resolve_session_id({"transcript_path": "/tmp/s.jsonl"})
        client = _FakeClient(
            {
                "results": [
                    {
                        "score": 0.9,
                        "memory": {
                            "partition_id": "mem_hippocampus",
                            "content": "From this very session",
                            "tags": [],
                            "metadata": {"session_id": derived},
                        },
                    },
                    {
                        "score": 0.8,
                        "memory": {
                            "partition_id": "mem_hippocampus",
                            "content": "From a previous session",
                            "tags": [],
                            "metadata": {"session_id": "other"},
                        },
                    },
                ]
            }
        )
        monkeypatch.setattr(
            recall,
            "read_hook_input",
            lambda: {"transcript_path": "/tmp/s.jsonl", "prompt": "ping me with context"},
        )
        monkeypatch.setattr(recall, "get_client", lambda timeout=5: client)
        recall.handle_prompt()
        out = capsys.readouterr().out
        assert "From this very session" not in out
        assert "From a previous session" in out


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
                            {"type": "tool_use", "name": "mcp__hebb__search_memory", "id": "t3", "input": {}},
                        ],
                    },
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.tools == ["Read", "Grep"]
        assert summary.mcps == ["mcp__hebb__search_memory"]

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

    def test_ignores_subagent_sidechain_lines(self, tmp_path: Path):
        """Subagent (Task) turns are written into the same JSONL tagged
        isSidechain:true. They must not contaminate the stored turn: the human
        prompt stays user_input and only main-agent tools are collected."""
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "isSidechain": False,
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "What is the capital of France?"}],
                    },
                },
                {
                    "type": "assistant",
                    "isSidechain": False,
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "name": "Task", "id": "a1", "input": {}}],
                    },
                },
                # --- subagent sidechain: must be dropped entirely ---
                {
                    "type": "user",
                    "isSidechain": True,
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "Search the codebase for capital lookups"}],
                    },
                },
                {
                    "type": "assistant",
                    "isSidechain": True,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "name": "Grep", "id": "s1", "input": {}},
                            {"type": "tool_use", "name": "mcp__hebb__search_memory", "id": "s2", "input": {}},
                        ],
                    },
                },
                # --- main agent resumes after the subagent ---
                {
                    "type": "assistant",
                    "isSidechain": False,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Paris."},
                            {"type": "tool_use", "name": "Edit", "id": "a2", "input": {}},
                        ],
                    },
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        # The human prompt is anchored, NOT the subagent's task prompt.
        assert summary.user_input == "What is the capital of France?"
        assert summary.assistant_output == "Paris."
        # Only main-agent tools; subagent Grep / MCP are excluded. Assert
        # membership (order is last-assistant-first then earlier assistants).
        assert set(summary.tools) == {"Task", "Edit"}
        assert "Grep" not in summary.tools
        assert summary.mcps == []
        # Turn index counts only the human turn (the sidechain user is dropped).
        assert summary.turn == 0

    def test_missing_issidechain_key_treated_as_main_agent(self, tmp_path: Path):
        """Lines without an isSidechain key (legacy transcripts and every
        existing fixture) are main-agent and must parse exactly as before."""
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Explain recursion"}]},
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "It calls itself."}]},
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.user_input == "Explain recursion"
        assert summary.assistant_output == "It calls itself."

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
        # Second human turn → 0-based turn index 1, so successive Stop writes
        # for one session stay ordered and can anchor turn-window expansion.
        assert summary.turn == 1

    def test_turn_index_ignores_tool_result_carriers(self, tmp_path: Path):
        """tool_result user messages (no human text) must not inflate the turn."""
        path = self._write_jsonl(
            tmp_path,
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Only human turn here"}]},
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "On it."}]},
                },
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]},
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]},
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.user_input == "Only human turn here"
        assert summary.turn == 0

    def test_extract_user_text_from_string_content(self, tmp_path: Path):
        """Claude Code stores a plain prompt as a bare string, not a block list."""
        path = self._write_jsonl(
            tmp_path,
            [
                {"type": "user", "message": {"role": "user", "content": "What is the capital of France?"}},
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "Paris."}]},
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.user_input == "What is the capital of France?"
        assert summary.assistant_output == "Paris."

    def test_skips_tool_result_carrier_to_find_prompt(self, tmp_path: Path):
        """When a turn ends with tool_result user messages, anchor on the human prompt."""
        path = self._write_jsonl(
            tmp_path,
            [
                {"type": "user", "message": {"role": "user", "content": "Create a config file for me please"}},
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "name": "Write", "id": "t1", "input": {}}],
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "File created"}],
                    },
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "Done — config written."}]},
                },
            ],
        )
        summary = extract_last_turn(path)
        assert summary is not None
        assert summary.user_input == "Create a config file for me please"
        assert summary.assistant_output == "Done — config written."
        assert summary.tools == ["Write"]

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
            mcps=["mcp__hebb__search_memory"],
        )
        result = format_turn_memory(summary)
        assert "[User] What is 1+1?" in result
        assert "[Assistant] The answer is 2." in result
        assert "[Tools] Read, Grep" in result
        assert "[MCP] mcp__hebb__search_memory" in result

    def test_skips_empty_sections(self):
        summary = TurnSummary(user_input="Hello", assistant_output="Hi")
        result = format_turn_memory(summary)
        assert "[Tools]" not in result
        assert "[MCP]" not in result

    def test_default_timestamp_is_second_precision(self):
        """The auto-generated prefix never carries sub-second digits."""
        result = format_turn_memory(TurnSummary(user_input="hi"))
        prefix = result.splitlines()[0]
        assert prefix.startswith("[") and prefix.endswith("]")
        # ISO second-precision has no '.' fractional-seconds group.
        assert "." not in prefix

    def test_explicit_millisecond_timestamp_truncated(self):
        """A transcript-style ms-precision ``...Z`` timestamp is truncated.

        Regression for #38: an explicit ``timestamp`` was passed through
        verbatim, leaking millisecond precision into the stored prefix.
        """
        result = format_turn_memory(
            TurnSummary(user_input="hi"),
            timestamp="2026-06-17T03:15:16.123Z",
        )
        assert result.startswith("[2026-06-17T03:15:16+00:00]")

    def test_explicit_microsecond_timestamp_truncated(self):
        result = format_turn_memory(
            TurnSummary(user_input="hi"),
            timestamp="2026-06-17T03:15:16.123456+00:00",
        )
        assert result.startswith("[2026-06-17T03:15:16+00:00]")

    def test_explicit_second_timestamp_preserved(self):
        """An already-clean timestamp passes through unchanged."""
        result = format_turn_memory(
            TurnSummary(user_input="hi"),
            timestamp="2026-06-17T03:15:16+00:00",
        )
        assert result.startswith("[2026-06-17T03:15:16+00:00]")

    def test_explicit_timestamp_preserves_offset(self):
        """A non-UTC offset survives truncation (only sub-seconds are dropped)."""
        result = format_turn_memory(
            TurnSummary(user_input="hi"),
            timestamp="2026-06-17T03:15:16.500+05:30",
        )
        assert result.startswith("[2026-06-17T03:15:16+05:30]")

    def test_malformed_timestamp_strips_subseconds_without_raising(self):
        """A timestamp ``fromisoformat`` cannot parse still loses sub-seconds.

        The fallback path must never raise — a bad timestamp cannot be allowed
        to abort the Stop hook's memory write.
        """
        result = format_turn_memory(
            TurnSummary(user_input="hi"),
            timestamp="not-a-real-2026-06-17T03:15:16.123 timestamp",
        )
        # Fractional seconds are gone; the rest is preserved verbatim.
        assert result.startswith("[not-a-real-2026-06-17T03:15:16 timestamp]")


class TestStopHook:
    def test_noop_without_transcript(self, monkeypatch: pytest.MonkeyPatch):
        """No transcript_path → no client opened, no memory written."""
        opened: list[str] = []
        monkeypatch.setattr(stop, "read_hook_input", lambda: {"session_id": "s1"})
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: opened.append("client"))
        stop.handle()
        assert opened == []

    def test_records_turn_with_project_tag(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
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

        # Simulate Claude Code running inside a checked-out git project.
        project_dir = tmp_path / "myproj"
        (project_dir / ".git").mkdir(parents=True)

        client = _FakeClient()
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(project_dir),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)

        stop.handle()

        assert len(client.calls) == 1
        path, payload = client.calls[0]
        assert path == "/api/v1/memories"
        assert "[User] Explain this code" in payload["content"]
        assert "[Assistant] This function does X." in payload["content"]
        assert "[Tools] Read" in payload["content"]
        # Project name is the only tag when running inside a git repo.
        assert payload["tags"] == ["myproj"]
        assert payload["metadata"]["tools"] == ["Read"]
        assert payload["source"] == "hook:stop"
        assert client.closed is True

    def test_records_turn_without_project_tag(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "What is 1+1?"}]},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "Two."}]},
                }
            )
            + "\n"
        )

        # cwd lives outside any git repo → no project tag, tags=[].
        non_repo = tmp_path / "scratch"
        non_repo.mkdir()

        client = _FakeClient()
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(non_repo),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)

        stop.handle()

        assert len(client.calls) == 1
        _, payload = client.calls[0]
        assert payload["tags"] == []

    def test_stores_turn_when_user_prompt_is_greeting(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Pure-greeting user message → still stored: greetings are kept as feedback."""
        transcript = tmp_path / "session.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": "Hi!"}]},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Hi! How can I help today?"}],
                    },
                }
            )
            + "\n"
        )

        client = _FakeClient()
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        stop.handle()
        assert len(client.calls) == 1
        _, payload = client.calls[0]
        assert "[User] Hi!" in payload["content"]
        assert "[Assistant] Hi! How can I help today?" in payload["content"]

    def test_skips_turn_when_user_prompt_is_only_a_code_paste(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Code-only user message → filters to empty → no memory written."""
        transcript = tmp_path / "session.jsonl"
        user_text = "```python\nfor i in range(3):\n    print(i)\n```"
        transcript.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": user_text}]},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "The loop is fine."}]},
                }
            )
            + "\n"
        )

        client = _FakeClient()
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        stop.handle()
        assert client.calls == []

    def test_records_turn_with_long_noisy_user_prompt_cleaned(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Substantive prose mixed with code/HTML/base64 → strip noise, keep prose."""
        transcript = tmp_path / "session.jsonl"
        user_text = (
            "I'm debugging why the migration is failing on prod. "
            "Here's the schema I tried:\n"
            "```sql\nALTER TABLE users ADD COLUMN x TEXT NOT NULL;\n```\n"
            "And the render snippet was <div class='err'>boom</div> "
            "plus a screenshot data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAA= "
            "Any ideas?"
        )
        transcript.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": [{"type": "text", "text": user_text}]},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Likely the column lacks a default."}],
                    },
                }
            )
            + "\n"
        )

        client = _FakeClient()
        monkeypatch.setattr(
            stop,
            "read_hook_input",
            lambda: {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": str(tmp_path),
            },
        )
        monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)
        stop.handle()

        assert len(client.calls) == 1
        _, payload = client.calls[0]
        # Prose around the noise survived.
        assert "debugging why the migration is failing" in payload["content"]
        assert "Any ideas?" in payload["content"]
        # All four kinds of noise are stripped from the stored memory.
        assert "ALTER TABLE" not in payload["content"]
        assert "<div" not in payload["content"]
        assert "iVBORw0KGgo" not in payload["content"]
        assert "```" not in payload["content"]
        # Assistant text always kept verbatim.
        assert "[Assistant] Likely the column lacks a default." in payload["content"]
