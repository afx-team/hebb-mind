"""Tests for ``hebb doctor``'s local-ML-stack diagnostic (issue #42)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from hebb.cli.commands.doctor import doctor_cmd
from hebb.config.init import initialize_workspace


def _set_config(home: Path, **overrides: object) -> None:
    config_path = home / "hebb.json"
    config = json.loads(config_path.read_text())
    config.update(overrides)
    config_path.write_text(json.dumps(config))


def test_doctor_flags_missing_ml_stack_for_local_provider(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        initialize_workspace(home)
        # Default config has embedding_provider=local + rerank_enabled=true, so a
        # local stack is required. Simulate a lean install (stack missing).
        monkeypatch.setattr("hebb.cli.commands.doctor._local_stack_importable", lambda: False)
        result = runner.invoke(doctor_cmd, [])

    assert result.exit_code == 0, result.output
    assert "ML stack" in result.output
    assert "[FAIL]" in result.output
    assert "hebb-mind[local]" in result.output


def test_doctor_ok_when_ml_stack_present(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        initialize_workspace(home)
        monkeypatch.setattr("hebb.cli.commands.doctor._local_stack_importable", lambda: True)
        result = runner.invoke(doctor_cmd, [])

    assert result.exit_code == 0, result.output
    assert "ML stack" in result.output
    assert "sentence-transformers importable" in result.output


def test_doctor_skips_ml_stack_check_for_api_only_config(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HEBB_HOME", str(home))
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        initialize_workspace(home)
        # API embedding + rerank disabled → no local stack needed → row skipped.
        _set_config(home, embedding_provider="api", rerank_enabled=False)

        def _fail_if_called() -> bool:
            raise AssertionError("_local_stack_importable must not run for an API-only config")

        monkeypatch.setattr("hebb.cli.commands.doctor._local_stack_importable", _fail_if_called)
        result = runner.invoke(doctor_cmd, [])

    assert result.exit_code == 0, result.output
    assert "ML stack" not in result.output
