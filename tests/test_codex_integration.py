"""Tests for Codex integration commands."""

from __future__ import annotations

import subprocess

from click.testing import CliRunner

from hebb.integrations.codex.cli import codex


def test_codex_install_runs_mcp_add(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("hebb.integrations.codex.cli.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("hebb.integrations.codex.cli.subprocess.run", fake_run)

    result = CliRunner().invoke(codex, ["install", "--scope", "user"])

    assert result.exit_code == 0, result.output
    assert calls == [["codex", "mcp", "add", "hebb", "--", "hebb-mcp"]]


def test_codex_uninstall_runs_mcp_remove(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("hebb.integrations.codex.cli.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("hebb.integrations.codex.cli.subprocess.run", fake_run)

    result = CliRunner().invoke(codex, ["uninstall"])

    assert result.exit_code == 0, result.output
    assert calls == [["codex", "mcp", "remove", "hebb"]]
