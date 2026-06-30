"""Tests for native Codex install and lifecycle hook behavior."""

from __future__ import annotations

import json
from pathlib import Path

from hebb.integrations.claude_code.transcript import TurnSummary
from hebb.integrations.codex import install, stop, uninstall
from hebb.integrations.codex.transcript import CodexTurn, extract_last_turn


def _record(record_type: str, payload: dict, timestamp: str = "2026-06-29T01:02:03.456Z") -> str:
    return json.dumps({"timestamp": timestamp, "type": record_type, "payload": payload})


def _message(role: str, text: str, *, timestamp: str = "2026-06-29T01:02:03.456Z") -> str:
    block_type = "output_text" if role == "assistant" else "input_text"
    return _record(
        "response_item",
        {"type": "message", "role": role, "content": [{"type": block_type, "text": text}]},
        timestamp,
    )


class _Response:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _Client:
    def __init__(self, items: list[dict] | None = None) -> None:
        self.items = items or []
        self.posts: list[tuple[str, dict]] = []
        self.closed = False

    def get(self, path: str, params: dict | None = None) -> _Response:
        return _Response({"items": self.items})

    def post(self, path: str, json: dict | None = None) -> _Response:
        self.posts.append((path, json or {}))
        return _Response()

    def close(self) -> None:
        self.closed = True


def test_codex_transcript_extracts_latest_turn_and_tools(tmp_path: Path) -> None:
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text(
        "\n".join(
            [
                _record("response_item", {"type": "message", "role": "developer", "content": []}),
                _message("user", "First substantive prompt"),
                _message("assistant", "First answer"),
                "{malformed",
                _message("user", "Please remember that this project uses pnpm.", timestamp="2026-06-29T02:03:04.567Z"),
                _record("response_item", {"type": "function_call", "name": "exec_command", "arguments": "{}"}),
                _record("response_item", {"type": "function_call", "name": "mcp__hebb__search_memory", "arguments": "{}"}),
                _record("response_item", {"type": "function_call", "name": "exec_command", "arguments": "{}"}),
                _message("assistant", "Transcript fallback answer"),
            ]
        )
        + "\n"
    )

    turn = extract_last_turn(transcript, last_assistant_message="Stable Stop-hook answer")

    assert turn is not None
    assert turn.timestamp == "2026-06-29T02:03:04.567Z"
    assert turn.summary.user_input == "Please remember that this project uses pnpm."
    assert turn.summary.assistant_output == "Stable Stop-hook answer"
    assert turn.summary.tools == ["exec_command"]
    assert turn.summary.mcps == ["mcp__hebb__search_memory"]
    assert turn.summary.turn == 1


def test_codex_transcript_falls_back_to_assistant_record(tmp_path: Path) -> None:
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text(
        "\n".join(
            [
                _message("user", "Explain why this integration test fails."),
                _message("assistant", "The fixture uses the wrong schema."),
            ]
        )
        + "\n"
    )

    turn = extract_last_turn(transcript)

    assert turn is not None
    assert turn.summary.assistant_output == "The fixture uses the wrong schema."


def test_project_install_is_idempotent_and_preserves_other_config(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / ".codex" / "config.toml"
    config.parent.mkdir()
    config.write_text(
        'model = "gpt-5.4"\n\n'
        "[mcp_servers.other]\n"
        'command = "other"\n\n'
        "[mcp_servers.hebb]\n"
        'command = "stale"\n'
        'args = ["old"]\n\n'
        "[mcp_servers.hebb.env]\n"
        'OLD = "1"\n\n'
        "[features]\n"
        "hooks = true\n"
    )
    hooks = tmp_path / ".codex" / "hooks.json"
    hooks.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "other recall"}]},
                        {"hooks": [{"type": "command", "command": "hebb claude-code recall"}]},
                    ]
                }
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(install, "hebb_command", lambda: ["/opt/hebb/bin/hebb"])
    monkeypatch.setattr(install, "hebb_mcp_command", lambda: ["/opt/hebb/bin/hebb-mcp"])

    install.handle("project")
    install.handle("project")

    config_text = config.read_text()
    assert config_text.count("[mcp_servers.hebb]") == 1
    assert 'command = "/opt/hebb/bin/hebb-mcp"' in config_text
    assert "[mcp_servers.other]" in config_text
    assert "[features]" in config_text
    assert "OLD" not in config_text

    hook_data = json.loads(hooks.read_text())
    commands = [
        handler["command"]
        for entries in hook_data["hooks"].values()
        for entry in entries
        for handler in entry["hooks"]
    ]
    assert commands.count("/opt/hebb/bin/hebb codex recall") == 1
    assert commands.count("/opt/hebb/bin/hebb codex prompt") == 1
    assert commands.count("/opt/hebb/bin/hebb codex stop") == 1
    assert "other recall" in commands
    assert all("claude-code" not in command for command in commands)


def test_project_uninstall_preserves_non_hebb_entries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(install, "hebb_command", lambda: ["/bin/hebb"])
    monkeypatch.setattr(install, "hebb_mcp_command", lambda: ["/bin/hebb-mcp"])
    install.handle("project")
    hooks = tmp_path / ".codex" / "hooks.json"
    data = json.loads(hooks.read_text())
    data["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "other stop"}]})
    hooks.write_text(json.dumps(data))

    uninstall.handle("project")

    assert "[mcp_servers.hebb]" not in (tmp_path / ".codex" / "config.toml").read_text()
    assert "other stop" in hooks.read_text()
    assert "hebb codex" not in hooks.read_text()


def test_codex_stop_writes_native_metadata(monkeypatch) -> None:
    client = _Client()
    summary = TurnSummary(
        user_input="Remember this project uses pnpm.",
        assistant_output="Recorded.",
        tools=["exec_command"],
        mcps=["mcp__hebb__search_memory"],
        turn=2,
    )
    hook_input = {
        "session_id": "session-1",
        "turn_id": "turn-3",
        "cwd": "/workspace/project",
        "transcript_path": "/tmp/rollout.jsonl",
        "last_assistant_message": "Recorded.",
    }
    monkeypatch.setattr(stop, "read_hook_input", lambda: hook_input)
    monkeypatch.setattr(stop, "detect_project_name", lambda cwd: "project")
    monkeypatch.setattr(
        stop,
        "extract_last_turn",
        lambda path, last_assistant_message=None: CodexTurn(summary, "2026-06-29T01:02:03.456Z"),
    )
    monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)

    stop.handle()

    assert client.closed is True
    assert len(client.posts) == 1
    payload = client.posts[0][1]
    assert payload["source"] == "hook:codex-stop"
    assert payload["tags"] == ["project"]
    assert payload["metadata"] == {
        "session_id": "session-1",
        "host": "codex",
        "tools": ["exec_command"],
        "mcps": ["mcp__hebb__search_memory"],
        "turn": 2,
        "turn_id": "turn-3",
    }
    assert payload["content"].startswith("[2026-06-29T01:02:03.456Z]")


def test_codex_stop_deduplicates_session_turn(monkeypatch) -> None:
    client = _Client(items=[{"metadata": {"session_id": "session-1", "turn": 0}}])
    summary = TurnSummary(user_input="A substantive prompt.", assistant_output="Done.", turn=0)
    monkeypatch.setattr(
        stop,
        "read_hook_input",
        lambda: {"session_id": "session-1", "transcript_path": "/tmp/rollout.jsonl"},
    )
    monkeypatch.setattr(stop, "detect_project_name", lambda cwd: None)
    monkeypatch.setattr(stop, "extract_last_turn", lambda *args, **kwargs: CodexTurn(summary))
    monkeypatch.setattr(stop, "get_client", lambda timeout=30: client)

    stop.handle()

    assert client.posts == []
