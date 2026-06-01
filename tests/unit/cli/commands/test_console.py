"""Tests for the `hebb console` CLI command."""

from __future__ import annotations

import httpx
import pytest
from click.testing import CliRunner

from hebb.cli.commands import console as console_cli


def _ok_response() -> object:
    class _Resp:
        def json(self) -> dict[str, str]:
            return {"status": "ok"}

    return _Resp()


def test_console_print_only_outputs_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(console_cli, "resolve_server_url", lambda: "http://127.0.0.1:8000")
    monkeypatch.setattr(console_cli.httpx, "get", lambda *a, **k: _ok_response())

    launched: list[str] = []
    monkeypatch.setattr(console_cli.click, "launch", lambda url: launched.append(url))

    runner = CliRunner()
    result = runner.invoke(console_cli.console_cmd, ["--print"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:8000" in result.output
    assert launched == []


def test_console_default_launches_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(console_cli, "resolve_server_url", lambda: "http://127.0.0.1:8000")
    monkeypatch.setattr(console_cli.httpx, "get", lambda *a, **k: _ok_response())

    launched: list[str] = []
    monkeypatch.setattr(console_cli.click, "launch", lambda url: launched.append(url))

    runner = CliRunner()
    result = runner.invoke(console_cli.console_cmd, [])
    assert result.exit_code == 0
    assert launched == ["http://127.0.0.1:8000/"]


def test_console_fails_when_server_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(console_cli, "resolve_server_url", lambda: "http://127.0.0.1:8000")

    def _refuse(*_a, **_k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(console_cli.httpx, "get", _refuse)

    launched: list[str] = []
    monkeypatch.setattr(console_cli.click, "launch", lambda url: launched.append(url))

    runner = CliRunner()
    result = runner.invoke(console_cli.console_cmd, [])
    assert result.exit_code != 0
    assert "hebb service install" in result.output
    assert launched == []
