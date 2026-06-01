"""Tests for the reembed checkpoint file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hebb.cli import reembed_checkpoint as cp_mod
from hebb.cli.reembed_checkpoint import (
    CHECKPOINT_FILENAME,
    SCHEMA_VERSION,
    ReembedCheckpoint,
)


def _make(workspace: Path, *, pending: list[str], partition: str | None = None) -> ReembedCheckpoint:
    return ReembedCheckpoint(
        target_model="BAAI/bge-m3",
        target_dim=1024,
        partition_id=partition,
        total=len(pending),
        pending_ids=list(pending),
    )


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    cp = _make(tmp_path, pending=["a", "b", "c"])
    cp_mod.save(cp, tmp_path)

    loaded = cp_mod.load(tmp_path)
    assert loaded is not None
    assert loaded.target_model == "BAAI/bge-m3"
    assert loaded.target_dim == 1024
    assert loaded.partition_id is None
    assert loaded.total == 3
    assert loaded.pending_ids == ["a", "b", "c"]
    assert loaded.schema_version == SCHEMA_VERSION


def test_load_returns_none_when_absent(tmp_path: Path) -> None:
    assert cp_mod.load(tmp_path) is None


def test_load_returns_none_on_corrupt_file(tmp_path: Path) -> None:
    (tmp_path / CHECKPOINT_FILENAME).write_text("{not valid json")
    assert cp_mod.load(tmp_path) is None


def test_load_returns_none_on_unknown_schema_version(tmp_path: Path) -> None:
    (tmp_path / CHECKPOINT_FILENAME).write_text(json.dumps({"schema_version": 9999}))
    assert cp_mod.load(tmp_path) is None


def test_save_is_atomic_no_stray_tmp_files(tmp_path: Path) -> None:
    cp = _make(tmp_path, pending=["a"])
    cp_mod.save(cp, tmp_path)
    leftovers = [p for p in tmp_path.iterdir() if p.name != CHECKPOINT_FILENAME]
    assert leftovers == []


def test_save_updates_updated_at(tmp_path: Path) -> None:
    cp = _make(tmp_path, pending=["a"])
    cp.updated_at = "1970-01-01T00:00:00+00:00"
    cp_mod.save(cp, tmp_path)
    loaded = cp_mod.load(tmp_path)
    assert loaded is not None
    assert loaded.updated_at != "1970-01-01T00:00:00+00:00"


def test_delete_removes_file(tmp_path: Path) -> None:
    cp = _make(tmp_path, pending=["a"])
    cp_mod.save(cp, tmp_path)
    assert cp_mod.delete(tmp_path) is True
    assert cp_mod.load(tmp_path) is None
    # Idempotent: second delete is a no-op.
    assert cp_mod.delete(tmp_path) is False


def test_matches_strict_on_all_three_keys(tmp_path: Path) -> None:
    cp = _make(tmp_path, pending=["a"], partition="mem_user")
    assert cp.matches(model="BAAI/bge-m3", dim=1024, partition_id="mem_user")
    # Any one differing → no match
    assert not cp.matches(model="other", dim=1024, partition_id="mem_user")
    assert not cp.matches(model="BAAI/bge-m3", dim=384, partition_id="mem_user")
    assert not cp.matches(model="BAAI/bge-m3", dim=1024, partition_id=None)


def test_summarize_reports_progress(tmp_path: Path) -> None:
    cp = ReembedCheckpoint(
        target_model="X",
        target_dim=384,
        partition_id=None,
        total=100,
        pending_ids=["a"] * 30,
    )
    s = cp_mod.summarize(cp)
    assert s["done"] == 70
    assert s["total"] == 100
    assert s["pct"] == pytest.approx(70.0)


def test_checkpoint_path_handles_none_workspace() -> None:
    assert cp_mod.checkpoint_path(None) is None
    assert cp_mod.load(None) is None
    assert cp_mod.delete(None) is False


def test_save_no_op_when_workspace_is_none() -> None:
    cp = ReembedCheckpoint(
        target_model="X", target_dim=1, partition_id=None, total=1, pending_ids=["a"]
    )
    # Must not raise.
    cp_mod.save(cp, None)
