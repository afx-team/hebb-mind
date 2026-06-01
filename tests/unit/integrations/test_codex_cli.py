"""Tests for Codex integration commands."""

from __future__ import annotations

import subprocess

from click.testing import CliRunner

from hebb.integrations.codex.cli import codex


def test_codex_install_runs_mcp_add(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], check: bool = False, **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("hebb.integrations.codex.cli.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("hebb.integrations.codex.cli.subprocess.run", fake_run)

    result = CliRunner().invoke(codex, ["install", "--scope", "user"])

    assert result.exit_code == 0, result.output
    # Codex install resolves hebb-mcp to an absolute path before handing it to
    # `codex mcp add`. It also pre-removes any prior entry so the install is
    # idempotent / picks up a moved binary.
    assert calls[0] == ["codex", "mcp", "remove", "hebb"]
    assert calls[1] == ["codex", "mcp", "add", "hebb", "--", "/bin/hebb-mcp"]


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
