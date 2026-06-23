"""Tests for the lightweight forgetting run tracker."""

from __future__ import annotations

import json
from pathlib import Path

from hebb.server import forgetting_tracker as tracker


def setup_function() -> None:
    tracker._runs.clear()
    tracker._logs_dir = None


def test_init_creates_dir(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs" / "forgetting"
    tracker.init_forgetting_tracker(logs_dir)
    assert logs_dir.is_dir()


def test_record_run_populates_fields(tmp_path: Path) -> None:
    tracker.init_forgetting_tracker(tmp_path)
    run = tracker.record_run(
        trigger="manual", started_at=1.0, scanned=10, deleted=3, partitions_swept=2
    )
    assert run.status == "done"
    assert run.trigger == "manual"
    assert run.scanned == 10
    assert run.deleted == 3
    assert run.partitions_swept == 2
    assert run.finished_at is not None
    assert tracker.list_runs() == [run]


def test_record_failed_run(tmp_path: Path) -> None:
    tracker.init_forgetting_tracker(tmp_path)
    run = tracker.record_run(
        trigger="scheduled", started_at=1.0, scanned=0, deleted=0,
        partitions_swept=0, status="failed", error="boom",
    )
    assert run.status == "failed"
    assert run.error == "boom"


def test_list_runs_most_recent_first(tmp_path: Path) -> None:
    tracker.init_forgetting_tracker(tmp_path)
    tracker.record_run(trigger="scheduled", started_at=1.0, scanned=1, deleted=0, partitions_swept=1)
    tracker.record_run(trigger="manual", started_at=2.0, scanned=2, deleted=1, partitions_swept=1)
    runs = tracker.list_runs()
    assert [r.started_at for r in runs] == [2.0, 1.0]


def test_prune_keeps_only_max_runs(tmp_path: Path) -> None:
    tracker.init_forgetting_tracker(tmp_path)
    for i in range(tracker.MAX_RUNS + 5):
        tracker.record_run(trigger="scheduled", started_at=float(i), scanned=0, deleted=0, partitions_swept=0)
    assert len(tracker.list_runs()) == tracker.MAX_RUNS


def test_manifest_roundtrip(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs" / "forgetting"
    tracker.init_forgetting_tracker(logs_dir)
    tracker.record_run(trigger="manual", started_at=5.0, scanned=7, deleted=2, partitions_swept=3)

    # Manifest is written atomically and is the source of truth.
    manifest = json.loads((logs_dir / "manifest.json").read_text())
    assert manifest[0]["scanned"] == 7

    # A fresh init reloads the persisted run.
    tracker._runs.clear()
    tracker.init_forgetting_tracker(logs_dir)
    runs = tracker.list_runs()
    assert len(runs) == 1
    assert runs[0].deleted == 2
