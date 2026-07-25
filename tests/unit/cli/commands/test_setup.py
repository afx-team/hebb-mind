"""Tests for setup CLI behavior."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from hebb.cli.commands.setup import setup_cmd
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
