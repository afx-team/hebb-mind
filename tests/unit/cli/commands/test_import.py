"""Tests for the ``hebb import`` command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from hebb.cli.commands import external_import as import_cli
from hebb.cli.main import main
from hebb.ingest.external import ImportSummary


def test_import_command_is_registered() -> None:
    result = CliRunner().invoke(main, ["import", "--help"])

    assert result.exit_code == 0, result.output
    assert "openhands" in result.output
    assert "openclaw" in result.output
    assert "hkuds" in result.output


def test_import_command_reports_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mind = MagicMock()
    mind.__enter__.return_value = mind
    monkeypatch.setattr(import_cli, "HebbMind", lambda: mind)
    monkeypatch.setattr(
        import_cli,
        "import_external_corpus",
        lambda source, path, target: ImportSummary(discovered=3, imported=2, skipped_existing=1),
    )

    result = CliRunner().invoke(main, ["import", "openclaw", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "2 imported" in result.output
    assert "1 already present" in result.output
