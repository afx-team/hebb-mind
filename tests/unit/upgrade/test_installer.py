"""Tests for hebb.upgrade.installer — install-method detection + commands."""

from __future__ import annotations

import os
import sys

import pytest

from hebb.upgrade import installer


def test_detect_editable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "_is_editable_install", lambda: True)
    assert installer.detect_method() == "editable"
    cmd = installer.build_command("editable")
    assert cmd.auto_upgradable is False
    assert cmd.argv == []
    assert cmd.refusal_reason


def test_detect_pipx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "_is_editable_install", lambda: False)
    monkeypatch.setattr(sys, "executable", "/home/u/.local/pipx/venvs/hebb-mind/bin/python")
    # Pin the tool path so the command is deterministic regardless of whether
    # pipx happens to be on PATH in the test environment.
    monkeypatch.setattr(installer.shutil, "which", lambda _name: "/opt/bin/pipx")
    assert installer.detect_method() == "pipx"
    cmd = installer.build_command("pipx")
    assert cmd.auto_upgradable is True
    assert cmd.argv[-2:] == ["upgrade", "hebb-mind"]


def test_detect_uv_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "_is_editable_install", lambda: False)
    monkeypatch.setattr(sys, "executable", "/home/u/.local/share/uv/tools/hebb-mind/bin/python")
    # uv is not preinstalled on CI runners — pin its path so build_command
    # produces the uv argv instead of refusing.
    monkeypatch.setattr(installer.shutil, "which", lambda _name: "/opt/bin/uv")
    assert installer.detect_method() == "uv-tool"
    cmd = installer.build_command("uv-tool")
    assert cmd.argv[-3:] == ["tool", "upgrade", "hebb-mind"]


def test_detect_pip_in_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "_is_editable_install", lambda: False)
    monkeypatch.setattr(installer, "_classify_executable", lambda: "pip")
    monkeypatch.setattr(installer, "_is_system_python", lambda: False)
    assert installer.detect_method() == "pip"
    cmd = installer.build_command("pip")
    assert cmd.auto_upgradable is True
    assert cmd.argv[:4] == [sys.executable, "-m", "pip", "install"]
    assert cmd.argv[-1] == "hebb-mind"


def test_detect_system_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "_is_editable_install", lambda: False)
    monkeypatch.setattr(installer, "_classify_executable", lambda: "pip")
    monkeypatch.setattr(installer, "_is_system_python", lambda: True)
    assert installer.detect_method() == "system"
    cmd = installer.build_command("system")
    assert cmd.auto_upgradable is False
    assert cmd.argv == []


def test_pip_honors_index_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEBB_PYPI_INDEX_URL", "https://mirror.example/simple")
    cmd = installer.build_command("pip")
    assert cmd.env.get("PIP_INDEX_URL") == "https://mirror.example/simple"


def test_uv_honors_index_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEBB_PYPI_INDEX_URL", "https://mirror.example/simple")
    # uv may not be on PATH (e.g. CI) — pin it so the uv command is built.
    monkeypatch.setattr(installer.shutil, "which", lambda _name: "/opt/bin/uv")
    cmd = installer.build_command("uv-tool")
    assert cmd.env.get("UV_INDEX_URL") == "https://mirror.example/simple"


def test_is_system_python_false_in_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "prefix", "/some/venv")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert installer._is_system_python() is False


# The system-root checks use Path.resolve(), whose drive semantics differ by OS
# (a POSIX-looking "/usr" becomes "c:/usr" on Windows and vice-versa), so the
# positive cases are split per platform.
@pytest.mark.skipif(os.name == "nt", reason="POSIX system roots")
def test_is_system_python_true_for_system_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert installer._is_system_python() is True


@pytest.mark.skipif(os.name == "nt", reason="POSIX system roots")
def test_is_system_python_case_insensitive_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    # Detection must be case-insensitive so an uppercase system prefix is never
    # misread as user-writable.
    monkeypatch.setattr(sys, "prefix", "/USR/local")
    monkeypatch.setattr(sys, "base_prefix", "/USR/local")
    assert installer._is_system_python() is True


@pytest.mark.skipif(os.name != "nt", reason="Windows system roots")
def test_is_system_python_case_insensitive_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    # Uppercase "C:\PROGRAM FILES" must still be recognized as system-managed.
    monkeypatch.setattr(sys, "prefix", "C:\\PROGRAM FILES\\Python312")
    monkeypatch.setattr(sys, "base_prefix", "C:\\PROGRAM FILES\\Python312")
    assert installer._is_system_python() is True


def test_pipx_falls_back_to_pip_when_pipx_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    cmd = installer.build_command("pipx")
    assert cmd.auto_upgradable is True
    assert cmd.argv[:4] == [sys.executable, "-m", "pip", "install"]


def test_uv_refused_when_uv_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    cmd = installer.build_command("uv-tool")
    assert cmd.auto_upgradable is False
    assert cmd.argv == []
    assert "uv" in (cmd.refusal_reason or "")


def _raise(_name: str) -> object:
    raise RuntimeError("no metadata")


def test_editable_heuristic_matches_hebb_source_tree(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = tmp_path / "repo" / "src" / "hebb"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (tmp_path / "repo" / "pyproject.toml").write_text('[project]\nname = "hebb-mind"\n')
    monkeypatch.setattr(installer.hebb, "__file__", str(pkg / "__init__.py"))
    monkeypatch.setattr(installer.Distribution, "from_name", staticmethod(_raise))
    assert installer._is_editable_install() is True


def test_editable_heuristic_ignores_unrelated_pyproject(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A normal (non-editable) install whose venv is nested under an UNRELATED
    # project must NOT be flagged editable just because a pyproject.toml exists
    # above site-packages.
    pkg = tmp_path / "proj" / "venv" / "lib" / "python" / "site-packages" / "hebb"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (tmp_path / "proj" / "pyproject.toml").write_text('[project]\nname = "user-app"\n')
    monkeypatch.setattr(installer.hebb, "__file__", str(pkg / "__init__.py"))
    monkeypatch.setattr(installer.Distribution, "from_name", staticmethod(_raise))
    assert installer._is_editable_install() is False
