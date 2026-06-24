"""Tests for hebb.upgrade.installer — install-method detection + commands."""

from __future__ import annotations

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
    assert installer.detect_method() == "pipx"
    cmd = installer.build_command("pipx")
    assert cmd.auto_upgradable is True
    assert cmd.argv[-2:] == ["upgrade", "hebb-mind"]


def test_detect_uv_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "_is_editable_install", lambda: False)
    monkeypatch.setattr(sys, "executable", "/home/u/.local/share/uv/tools/hebb-mind/bin/python")
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
    cmd = installer.build_command("uv-tool")
    assert cmd.env.get("UV_INDEX_URL") == "https://mirror.example/simple"


def test_is_system_python_false_in_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "prefix", "/some/venv")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert installer._is_system_python() is False


def test_is_system_python_true_for_system_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    assert installer._is_system_python() is True


def test_is_system_python_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    # Detection must be case-insensitive so an uppercase system prefix (seen on
    # Windows, e.g. C:\PROGRAM FILES) is never misread as user-writable. Use a
    # POSIX uppercase root here since Path.resolve() drive semantics differ by OS.
    monkeypatch.setattr(sys, "prefix", "/USR/local")
    monkeypatch.setattr(sys, "base_prefix", "/USR/local")
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
