"""Tests for CLI command path resolution."""

from __future__ import annotations

from pathlib import Path

from hebb.utils import cli_paths


def test_source_checkout_command_uses_checkout_pythonpath(monkeypatch, tmp_path: Path) -> None:
    """Source installs must not reinstall a stale global ``hebb`` binary."""
    python = tmp_path / ".venv" / "bin" / "python"
    monkeypatch.setattr(cli_paths, "_source_checkout_root", lambda: tmp_path)
    monkeypatch.setattr(cli_paths, "_preferred_python", lambda root: python)
    monkeypatch.setattr(cli_paths.os, "name", "posix")

    assert cli_paths.hebb_command() == [
        "/usr/bin/env",
        f"PYTHONPATH={tmp_path / 'src'}",
        str(python),
        "-m",
        "hebb.cli.main",
    ]
    assert cli_paths.hebb_mcp_command() == [
        "/usr/bin/env",
        f"PYTHONPATH={tmp_path / 'src'}",
        str(python),
        "-m",
        "hebb.mcp.server",
    ]


def test_installed_binary_is_used_outside_source_checkout(monkeypatch) -> None:
    """Packaged installs should continue to use the resolved entry points."""
    monkeypatch.setattr(cli_paths, "_source_checkout_command", lambda module: None)
    monkeypatch.setattr(cli_paths.shutil, "which", lambda name: f"/bin/{name}")

    assert cli_paths.hebb_command() == ["/bin/hebb"]
    assert cli_paths.hebb_mcp_command() == ["/bin/hebb-mcp"]
