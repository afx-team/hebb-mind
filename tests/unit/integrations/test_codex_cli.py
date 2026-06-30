"""Tests for Codex integration commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from hebb.integrations.codex import install as install_module
from hebb.integrations.codex import uninstall as uninstall_module
from hebb.integrations.codex.cli import codex


def test_codex_user_install_runs_mcp_add(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], check: bool = False, **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("hebb.integrations.codex.cli.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(install_module, "hebb_command", lambda: ["/bin/hebb"])
    monkeypatch.setattr(install_module, "hebb_mcp_command", lambda: ["/bin/hebb-mcp"])
    monkeypatch.setattr(install_module, "config_path", lambda scope: tmp_path / "config.toml")
    monkeypatch.setattr(install_module, "hooks_path", lambda scope: tmp_path / "hooks.json")
    monkeypatch.setattr(install_module.subprocess, "run", fake_run)

    result = CliRunner().invoke(codex, ["install", "--scope", "user"])

    assert result.exit_code == 0, result.output
    assert calls[0] == ["codex", "mcp", "remove", "hebb"]
    assert calls[1] == ["codex", "mcp", "add", "hebb", "--", "/bin/hebb-mcp"]
    assert "hebb codex recall" in (tmp_path / "hooks.json").read_text()


def test_codex_user_uninstall_runs_mcp_remove(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], check: bool = False, **kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("hebb.integrations.codex.cli.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(uninstall_module, "hooks_path", lambda scope: tmp_path / "hooks.json")
    monkeypatch.setattr(uninstall_module.subprocess, "run", fake_run)

    result = CliRunner().invoke(codex, ["uninstall", "--scope", "user"])

    assert result.exit_code == 0, result.output
    assert calls == [["codex", "mcp", "remove", "hebb"]]


def test_codex_defaults_to_project_scope(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hebb.integrations.codex.cli.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(install_module, "hebb_command", lambda: ["/bin/hebb"])
    monkeypatch.setattr(install_module, "hebb_mcp_command", lambda: ["/bin/hebb-mcp"])

    result = CliRunner().invoke(codex, ["install"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".codex" / "config.toml").exists()
    assert (tmp_path / ".codex" / "hooks.json").exists()
