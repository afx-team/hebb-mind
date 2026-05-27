"""Tests for hebb.upgrade.state — atomic IO + tolerance for missing/corrupt files."""

from __future__ import annotations

import json
from pathlib import Path

from hebb.upgrade import state as upgrade_state
from hebb.upgrade.state import LastUpgrade, UpgradeState


def test_load_returns_default_when_missing(tmp_path: Path) -> None:
    state = upgrade_state.load(tmp_path)
    assert state == UpgradeState()
    assert state.available is False
    assert state.current_version == ""


def test_load_returns_default_when_corrupt(tmp_path: Path) -> None:
    (tmp_path / "upgrade_state.json").write_text("{ not valid json")
    state = upgrade_state.load(tmp_path)
    assert state == UpgradeState()


def test_load_returns_default_when_schema_mismatch(tmp_path: Path) -> None:
    # Wrong types for typed fields → Pydantic validation should fail gracefully.
    (tmp_path / "upgrade_state.json").write_text(json.dumps({"available": "not-a-bool"}))
    state = upgrade_state.load(tmp_path)
    assert state == UpgradeState()


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    written = UpgradeState(
        current_version="0.1.3",
        latest_version="0.2.0",
        checked_at="2026-05-27T12:00:00+00:00",
        available=True,
        notified_for_version="0.2.0",
    )
    upgrade_state.save(tmp_path, written)
    read = upgrade_state.load(tmp_path)
    assert read == written


def test_save_is_atomic(tmp_path: Path) -> None:
    # After save, no leftover .tmp files should remain in the directory.
    upgrade_state.save(tmp_path, UpgradeState(current_version="0.1.3"))
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".upgrade_state")]
    assert leftovers == []


def test_update_merges_changes(tmp_path: Path) -> None:
    upgrade_state.save(tmp_path, UpgradeState(current_version="0.1.3", available=False))
    new = upgrade_state.update(tmp_path, available=True, latest_version="0.1.4")
    assert new.current_version == "0.1.3"  # preserved
    assert new.available is True
    assert new.latest_version == "0.1.4"


def test_state_with_last_upgrade_roundtrip(tmp_path: Path) -> None:
    state = UpgradeState(
        current_version="0.1.4",
        last_upgrade=LastUpgrade(
            from_version="0.1.3",
            to_version="0.1.4",
            started_at="2026-05-27T12:00:00+00:00",
            finished_at="2026-05-27T12:01:00+00:00",
            status="success",
            method="pipx",
            log_tail="installed hebb-mind 0.1.4",
        ),
    )
    upgrade_state.save(tmp_path, state)
    loaded = upgrade_state.load(tmp_path)
    assert loaded.last_upgrade is not None
    assert loaded.last_upgrade.status == "success"
    assert loaded.last_upgrade.method == "pipx"
