"""Tests for the `hebb agent-sync` CLI command."""

from __future__ import annotations

import httpx
import pytest
from click.testing import CliRunner

from hebb.cli.commands import agent_sync as agent_sync_cli
from hebb.cli.main import main


class _Resp:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class _FailingResp:
    status_code = 404

    def raise_for_status(self) -> None:
        request = httpx.Request("GET", "http://127.0.0.1:8765/api/v1/agent-sync/sessions")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("not found", request=request, response=response)


def test_agent_sync_list_filters_claude_code(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_get(url: str, **kwargs: object) -> _Resp:
        calls.append({"url": url, **kwargs})
        return _Resp(
            [
                {
                    "id": "s1",
                    "host": "claude_code",
                    "project": "hippocampus",
                    "turn_count": 3,
                    "synced_turns": 1,
                    "unsynced_turns": 2,
                    "latest_timestamp": "2026-07-01T01:02:03Z",
                }
            ]
        )

    monkeypatch.setattr(agent_sync_cli, "resolve_server_url", lambda: "http://127.0.0.1:8765")
    monkeypatch.setattr(agent_sync_cli.httpx, "get", fake_get)

    result = CliRunner().invoke(agent_sync_cli.agent_sync_cmd, ["list", "--host", "claude-code"])

    assert result.exit_code == 0, result.output
    assert "Claude Code" in result.output
    assert "hippocampus" in result.output
    assert calls[0]["url"] == "http://127.0.0.1:8765/api/v1/agent-sync/sessions"
    assert calls[0]["params"] == {"host": "claude_code"}


def test_agent_sync_sync_posts_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_post(url: str, **kwargs: object) -> _Resp:
        calls.append({"url": url, **kwargs})
        return _Resp(
            {
                "sessions_scanned": 1,
                "turns_found": 3,
                "memories_created": 2,
                "skipped_existing": 1,
                "failed": 0,
                "dry_run": True,
                "items": [
                    {
                        "host": "codex",
                        "project": "hippocampus",
                        "turns_found": 3,
                        "memories_created": 2,
                        "skipped_existing": 1,
                        "failed": 0,
                    }
                ],
            }
        )

    monkeypatch.setattr(agent_sync_cli, "resolve_server_url", lambda: "http://127.0.0.1:8765")
    monkeypatch.setattr(agent_sync_cli.httpx, "post", fake_post)

    result = CliRunner().invoke(
        agent_sync_cli.agent_sync_cmd,
        ["sync", "--host", "codex", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output
    assert "2 created" in result.output
    assert calls[0]["url"] == "http://127.0.0.1:8765/api/v1/agent-sync/sync"
    assert calls[0]["json"] == {"host": "codex", "dry_run": True}


def test_agent_sync_main_command_is_registered() -> None:
    result = CliRunner().invoke(main, ["agent-sync", "--help"])

    assert result.exit_code == 0, result.output
    assert "list" in result.output
    assert "sync" in result.output


def test_agent_sync_host_help_uses_user_facing_names() -> None:
    result = CliRunner().invoke(agent_sync_cli.agent_sync_cmd, ["list", "--help"])

    assert result.exit_code == 0, result.output
    assert "--host [claude-code|codex]" in result.output
    assert "claude_code" not in result.output
    assert "all|" not in result.output
    assert "--limit" not in result.output
    assert "--url" not in result.output
    assert "--json" not in result.output


def test_agent_sync_sync_help_hides_internal_options() -> None:
    result = CliRunner().invoke(agent_sync_cli.agent_sync_cmd, ["sync", "--help"])

    assert result.exit_code == 0, result.output
    assert "--host [claude-code|codex]" in result.output
    assert "--dry-run" in result.output
    assert "--id" not in result.output
    assert "--limit" not in result.output
    assert "--url" not in result.output
    assert "--json" not in result.output


def test_agent_sync_unreachable_prints_service_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*_args: object, **_kwargs: object) -> _Resp:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(agent_sync_cli, "resolve_server_url", lambda: "http://127.0.0.1:8765")
    monkeypatch.setattr(agent_sync_cli.httpx, "get", fake_get)

    result = CliRunner().invoke(agent_sync_cli.agent_sync_cmd, ["list"])

    assert result.exit_code == 1
    assert "Cannot reach http://127.0.0.1:8765" in result.output
    assert "hebb service install" in result.output


def test_agent_sync_missing_api_prints_restart_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_sync_cli, "resolve_server_url", lambda: "http://127.0.0.1:8765")
    monkeypatch.setattr(agent_sync_cli.httpx, "get", lambda *_args, **_kwargs: _FailingResp())

    result = CliRunner().invoke(agent_sync_cli.agent_sync_cmd, ["list"])

    assert result.exit_code == 1
    assert "Agent Sync API failed" in result.output
    assert "older than this checkout" in result.output
    assert "--url" not in result.output
