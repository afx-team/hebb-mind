"""Tests for service installation helpers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from hippocampus.cli.commands import service


def _completed(args: list[str], returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr="")


def test_install_launchd_verifies_service_is_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plist_path = tmp_path / "com.hippocampus.server.plist"
    calls: list[list[str]] = []
    loaded = False

    def fake_run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal loaded
        calls.append(args)
        if args[0] == "bootout":
            loaded = False
            return _completed(args, 0)
        if args[0] == "bootstrap":
            loaded = True
            return _completed(args, 0)
        if args[0] == "print":
            return _completed(args, 0 if loaded else 1)
        return _completed(args, 0)

    monkeypatch.setattr(service, "LAUNCHD_PATH", plist_path)
    monkeypatch.setattr(service, "_hippocampus_bin", lambda: "/usr/local/bin/hippocampus")
    monkeypatch.setattr(service, "_working_dir", lambda: str(tmp_path))
    monkeypatch.setattr(service, "_run_launchctl", fake_run_launchctl)

    service._install_launchd()

    assert plist_path.exists()
    assert ["bootstrap", f"gui/{os.getuid()}", str(plist_path)] in calls
    assert ["kickstart", "-k", f"gui/{os.getuid()}/com.hippocampus.server"] in calls
    assert ["print", f"gui/{os.getuid()}/com.hippocampus.server"] in calls


def test_install_launchd_exits_when_launchctl_cannot_register(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plist_path = tmp_path / "com.hippocampus.server.plist"
    calls: list[list[str]] = []

    def fake_run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _completed(args, 5)

    monkeypatch.setattr(service, "LAUNCHD_PATH", plist_path)
    monkeypatch.setattr(service, "_hippocampus_bin", lambda: "/usr/local/bin/hippocampus")
    monkeypatch.setattr(service, "_working_dir", lambda: str(tmp_path))
    monkeypatch.setattr(service, "_run_launchctl", fake_run_launchctl)

    with pytest.raises(SystemExit):
        service._install_launchd()

    assert ["bootstrap", f"gui/{os.getuid()}", str(plist_path)] in calls
    assert ["load", str(plist_path)] in calls
