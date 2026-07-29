"""Tests for setup CLI behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from hebb.cli.commands.setup import _build_ml_stack_argv, _ensure_ml_stack, setup_cmd
from hebb.config.init import initialize_workspace


def _clear_locale_env(monkeypatch) -> None:
    for key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        monkeypatch.delenv(key, raising=False)


def test_setup_initializes_and_selects_english_model(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    _clear_locale_env(monkeypatch)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr(
        "hebb.cli.commands.setup.prefetch_model",
        lambda model_id, workspace, hf_endpoint=None, progress_callback=None, suppress_native_progress=False: (
            workspace / "models" / model_id
        ),
    )
    monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 384)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(setup_cmd, ["--region", "global"])

    assert result.exit_code == 0, result.output
    config = json.loads((home / "hebb.json").read_text())
    # Default profile selects a SMALL model (no eager multi-GB download).
    assert config["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert config["embedding_dim"] == 384
    assert config["hf_endpoint"] is None


def test_setup_initializes_and_selects_chinese_model(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    _clear_locale_env(monkeypatch)
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    monkeypatch.setattr(
        "hebb.cli.commands.setup.prefetch_model",
        lambda model_id, workspace, hf_endpoint=None, progress_callback=None, suppress_native_progress=False: (
            workspace / "models" / model_id
        ),
    )
    monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 384)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(setup_cmd, ["--region", "global"])

    assert result.exit_code == 0, result.output
    config = json.loads((home / "hebb.json").read_text())
    # zh default -> small multilingual model (~470MB), not the 1-2GB bge-m3.
    assert config["embedding_model"] == "intfloat/multilingual-e5-small"
    assert config["embedding_dim"] == 384


def test_setup_best_profile_selects_bge_english(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    _clear_locale_env(monkeypatch)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr(
        "hebb.cli.commands.setup.prefetch_model",
        lambda model_id, workspace, hf_endpoint=None, progress_callback=None, suppress_native_progress=False: (
            workspace / "models" / model_id
        ),
    )
    monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 1024)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(setup_cmd, ["--profile", "best", "--region", "global"])

    assert result.exit_code == 0, result.output
    config = json.loads((home / "hebb.json").read_text())
    # best is the explicit high-quality opt-in tier.
    assert config["embedding_model"] == "BAAI/bge-large-en-v1.5"
    assert config["embedding_dim"] == 1024


def test_setup_explicit_language_and_region_are_independent(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    monkeypatch.setattr(
        "hebb.cli.commands.setup.prefetch_model",
        lambda model_id, workspace, hf_endpoint=None, progress_callback=None, suppress_native_progress=False: (
            workspace / "models" / model_id
        ),
    )
    monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 384)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(setup_cmd, ["--language", "en", "--region", "cn"])

    assert result.exit_code == 0, result.output
    config = json.loads((home / "hebb.json").read_text())
    # Explicit language with default profile still selects the SMALL model.
    assert config["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert config["hf_endpoint"] == "https://hf-mirror.com"


def test_setup_keeps_custom_model_without_explicit_language(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        initialize_workspace(home)

        config_path = home / "hebb.json"
        config = json.loads(config_path.read_text())
        config["embedding_model"] = "custom/model"
        config["embedding_dim"] = 777
        config_path.write_text(json.dumps(config))

        monkeypatch.setattr(
            "hebb.cli.commands.setup.prefetch_model",
            lambda model_id, workspace, hf_endpoint=None, progress_callback=None, suppress_native_progress=False: (
                workspace / "models" / model_id
            ),
        )
        monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 777)
        result = runner.invoke(setup_cmd, ["--region", "global"])

        assert result.exit_code == 0, result.output
        updated = json.loads(config_path.read_text())
        assert updated["embedding_model"] == "custom/model"
        assert updated["embedding_dim"] == 777


def test_setup_skips_prefetch_when_model_already_present(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    _clear_locale_env(monkeypatch)
    monkeypatch.setenv("LANG", "en_US.UTF-8")

    # Model already cached in the workspace -> setup must NOT download.
    monkeypatch.setattr("hebb.cli.commands.setup.workspace_model_available", lambda workspace, model_id: True)

    called = {"prefetch": False}

    def _fail_prefetch(*args: object, **kwargs: object) -> Path:
        called["prefetch"] = True
        raise AssertionError("prefetch_model must not run when the model is already present")

    monkeypatch.setattr("hebb.cli.commands.setup.prefetch_model", _fail_prefetch)
    # _verify_model still runs against the cached model.
    monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 384)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(setup_cmd, ["--region", "global"])

    assert result.exit_code == 0, result.output
    assert called["prefetch"] is False
    assert "Model already present" in result.output
    assert "Downloading embedding model" not in result.output
    config = json.loads((home / "hebb.json").read_text())
    assert config["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert config["embedding_dim"] == 384


def test_setup_renders_live_download_progress(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    _clear_locale_env(monkeypatch)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr("hebb.cli.commands.setup.workspace_model_available", lambda workspace, model_id: False)

    callback_received = False

    def fake_prefetch(
        model_id: str,
        workspace: Path,
        hf_endpoint: str | None = None,
        progress_callback=None,
        suppress_native_progress: bool = False,
    ) -> Path:
        nonlocal callback_received
        assert progress_callback is not None
        assert suppress_native_progress is True
        callback_received = True
        progress_callback(512, 1024, "model.safetensors")
        progress_callback(1024, 1024, "model.safetensors")
        progress_callback(12, 12, "Fetching 12 files")
        return workspace / "models" / model_id

    monkeypatch.setattr("hebb.cli.commands.setup.prefetch_model", fake_prefetch)
    monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 384)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(setup_cmd, ["--region", "global"])

    assert result.exit_code == 0, result.output
    assert callback_received is True
    assert "model.safetensors" in result.output
    assert "small ~90MB" in result.output
    assert "100%" in result.output
    assert "Fetching 12 files" not in result.output


def test_initialize_workspace_uses_hebb_home(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))

    initialize_workspace()

    assert (home / "hebb.json").is_file()
    assert (home / "hebb.db").is_file()


# --- hebb setup on-demand ML-stack install (issue #42) ---
#
# `hebb setup` now auto-installs sentence-transformers + CPU torch when the
# stack is missing (User Path Ownership). The tests below exercise the
# installer helpers directly (the real `_ensure_ml_stack` / `_build_ml_stack_argv`
# are bound at module import, before the autouse stub below patches the module
# global that `setup_cmd` itself calls).


@pytest.fixture(autouse=True)
def _stub_ml_stack_for_setup_cmd(monkeypatch):
    """No-op the installer for `setup_cmd`-path tests so they never hit pip.

    In the lean CI `test` env (no `local` extra) `hebb setup` would otherwise
    shell out to pip. Tests that exercise the installer itself call the real
    helpers directly and are unaffected (they bind the real objects above).
    """
    monkeypatch.setattr("hebb.cli.commands.setup._ensure_ml_stack", lambda console: None)


def test_ensure_ml_stack_noop_when_stack_present(monkeypatch) -> None:
    # When the stack imports, _ensure_ml_stack must return without calling pip.
    monkeypatch.setattr("hebb.cli.commands.setup._ml_stack_present", lambda: True)

    def _fail_if_pip_called(*args: object, **kwargs: object) -> int:
        raise AssertionError("pip must not run when the stack is already present")

    monkeypatch.setattr(subprocess, "run", _fail_if_pip_called)

    _ensure_ml_stack(MagicMock())  # real function — returns None, no subprocess.


def test_build_ml_stack_argv_adds_cpu_index_off_darwin() -> None:
    argv, env = _build_ml_stack_argv("pip", use_cpu_torch=True, mirror=None)
    assert "sentence-transformers>=3.0.0" in argv
    assert "--extra-index-url" in argv
    assert "https://download.pytorch.org/whl/cpu" in argv
    assert env == {}

    # macOS path: CPU index omitted (PyPI torch is already CPU-only there).
    argv_mac, _ = _build_ml_stack_argv("pip", use_cpu_torch=False, mirror=None)
    assert "https://download.pytorch.org/whl/cpu" not in argv_mac


def test_build_ml_stack_argv_mirror_sets_pip_index_env() -> None:
    _argv, env = _build_ml_stack_argv(
        "pip", use_cpu_torch=False, mirror="https://mirror.example/simple"
    )
    assert env == {"PIP_INDEX_URL": "https://mirror.example/simple"}


def test_build_ml_stack_argv_uv_tool_without_uv_raises(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(click.ClickException, match="uv"):
        _build_ml_stack_argv("uv-tool", use_cpu_torch=False, mirror=None)


def test_ensure_ml_stack_refuses_system_python(monkeypatch) -> None:
    monkeypatch.setattr("hebb.cli.commands.setup._ml_stack_present", lambda: False)
    monkeypatch.setattr("hebb.upgrade.installer._is_system_python", lambda: True)

    def _fail_if_pip_called(*args: object, **kwargs: object) -> int:
        raise AssertionError("pip must not run for a system-managed Python")

    monkeypatch.setattr(subprocess, "run", _fail_if_pip_called)

    with pytest.raises(click.ClickException, match="system-managed Python"):
        _ensure_ml_stack(MagicMock())


def test_ensure_ml_stack_raises_click_exception_on_pip_failure(monkeypatch) -> None:
    monkeypatch.setattr("hebb.cli.commands.setup._ml_stack_present", lambda: False)
    monkeypatch.setattr("hebb.upgrade.installer._is_system_python", lambda: False)
    monkeypatch.setattr("hebb.upgrade.installer._classify_executable", lambda: "pip")

    def _pip_fails(*args: object, **kwargs: object) -> int:
        raise subprocess.CalledProcessError(returncode=1, cmd=["pip", "install"])

    monkeypatch.setattr(subprocess, "run", _pip_fails)

    with pytest.raises(click.ClickException, match="Failed to install the local ML stack"):
        _ensure_ml_stack(MagicMock())


def test_setup_does_not_persist_model_when_ml_stack_install_fails(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        initialize_workspace(home)
        config_path = home / "hebb.json"
        config = json.loads(config_path.read_text())
        # A pre-existing custom model + dim; setup must NOT overwrite these when
        # the stack install fails (install-F8: no unusable model persisted).
        config["embedding_model"] = "custom/model"
        config["embedding_dim"] = 777
        config_path.write_text(json.dumps(config))

        def _raise_stack_install(console: object) -> None:
            raise click.ClickException("simulated stack install failure")

        # Override the autouse no-op so setup_cmd hits a failing installer.
        monkeypatch.setattr("hebb.cli.commands.setup._ensure_ml_stack", _raise_stack_install)
        monkeypatch.setattr(
            "hebb.cli.commands.setup.prefetch_model",
            lambda model_id, workspace, hf_endpoint=None, progress_callback=None, suppress_native_progress=False: (
                workspace / "models" / model_id
            ),
        )
        monkeypatch.setattr("hebb.cli.commands.setup._verify_model", lambda model_id, hf_endpoint: 384)

        # --language en forces model selection (should_select_model=True), so on
        # success setup would overwrite embedding_model with all-MiniLM-L6-v2.
        result = runner.invoke(setup_cmd, ["--language", "en", "--region", "global"])

    assert result.exit_code != 0, result.output
    assert "Model setup failed" in result.output
    updated = json.loads(config_path.read_text())
    # F8: the prior (working) config is left untouched on failure.
    assert updated["embedding_model"] == "custom/model"
    assert updated["embedding_dim"] == 777
