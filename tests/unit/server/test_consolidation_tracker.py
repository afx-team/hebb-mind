"""Tests for the consolidation run tracker."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from hebb.server import consolidation_tracker as tracker


def _make_stale(run: tracker.ConsolidationRun) -> None:
    """Age a run's heartbeat *and* its log-file mtime past the stale threshold.

    Liveness is ``max(last_heartbeat, log_mtime)``, so a run created moments ago
    (whose log file was just touched) is only stale once both signals are old.
    """
    old = time.time() - tracker.STALE_AFTER_SECONDS - 10
    run.last_heartbeat = old
    if tracker._logs_dir is not None and run.log_file:
        log_path = tracker._logs_dir / run.log_file
        if log_path.exists():
            os.utime(log_path, (old, old))


@dataclass
class _FakeResult:
    original_memory_id: str
    success: bool = True
    error: str | None = None


def setup_function() -> None:
    tracker._runs.clear()
    tracker._handlers.clear()
    tracker._logs_dir = None


def test_init_creates_dir(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs" / "consolidation"
    tracker.init_tracker(logs_dir)
    assert logs_dir.is_dir()


def test_create_run(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    assert run.status == "running"
    assert run.trigger == "manual"
    assert run.log_file.startswith("run-")
    assert tracker.get_run(run.run_id) is run


def test_finish_run_populates_counters(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    results = [
        _FakeResult("m1", success=True),
        _FakeResult("m2", success=True),
        _FakeResult("m3", success=False, error="oops"),
    ]
    tracker.finish_run(run.run_id, results)
    assert run.status == "done"
    assert run.processed == 3
    assert run.succeeded == 2
    assert run.failed == 1
    assert run.finished_at is not None
    assert run.errors == [{"memory_id": "m3", "error": "oops"}]


def test_fail_run(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("scheduled")
    tracker.fail_run(run.run_id, "LLM timeout")
    assert run.status == "failed"
    assert run.finished_at is not None
    assert run.errors[0]["error"] == "LLM timeout"


def test_get_current_run(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    assert tracker.get_current_run() is None
    run = tracker.create_run("manual")
    assert tracker.get_current_run() is run
    tracker.finish_run(run.run_id, [])
    assert tracker.get_current_run() is None


def test_list_runs_ordering(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    r1 = tracker.create_run("manual")
    r2 = tracker.create_run("scheduled")
    runs = tracker.list_runs()
    assert runs[0].run_id == r2.run_id
    assert runs[1].run_id == r1.run_id


def test_prune_old_runs(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run_ids = []
    for i in range(25):
        r = tracker.create_run("manual")
        tracker.finish_run(r.run_id, [])
        run_ids.append(r.run_id)
    assert len(tracker._runs) == tracker.MAX_RUNS
    # Oldest runs should be pruned
    for old_id in run_ids[:5]:
        assert tracker.get_run(old_id) is None


def test_manifest_persistence(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    tracker.finish_run(run.run_id, [_FakeResult("m1")])

    # Simulate restart: clear in-memory state and reload
    tracker._runs.clear()
    tracker.init_tracker(tmp_path)
    reloaded = tracker.get_run(run.run_id)
    assert reloaded is not None
    assert reloaded.status == "done"
    assert reloaded.processed == 1
    assert reloaded.succeeded == 1


def test_crash_recovery(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("scheduled")
    # Simulate crash: run is still "running" in manifest
    tracker._detach_log_handler(run.run_id)
    tracker._runs.clear()
    reaped = tracker.init_tracker(tmp_path)
    # init_tracker reports how many runs it reaped, so the caller can resume.
    assert reaped == 1
    recovered = tracker.get_run(run.run_id)
    assert recovered is not None
    # An unfinished run is "interrupted" (will resume), distinct from "failed".
    assert recovered.status == "interrupted"
    assert recovered.finished_at is not None
    assert recovered.errors and recovered.errors[0]["error"]


def test_init_tracker_returns_zero_when_clean(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    tracker.finish_run(run.run_id, [])
    tracker._runs.clear()
    # A finished run is not reaped, so nothing to resume.
    assert tracker.init_tracker(tmp_path) == 0


def test_heartbeat_keeps_run_alive(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    # Push the heartbeat just past the stale threshold, then refresh it.
    _make_stale(run)
    tracker.heartbeat(run.run_id)
    # Heartbeat refreshed → still running, not reaped on read.
    assert tracker.get_current_run() is run
    assert run.status == "running"


def test_stale_running_run_is_reaped_on_read(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    # Simulate a stalled run: heartbeat (and log) silent past the threshold.
    _make_stale(run)
    # Reading the current run reaps it instead of returning a stuck "running".
    assert tracker.get_current_run() is None
    assert run.status == "interrupted"
    assert run.finished_at is not None


def test_heartbeat_ignores_finished_run(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    tracker.finish_run(run.run_id, [])
    before = run.last_heartbeat
    tracker.heartbeat(run.run_id)
    # A finished run must not be resurrected to "running" by a late heartbeat.
    assert run.status == "done"
    assert run.last_heartbeat == before


def test_get_or_create_run_dedupes_live_run(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    first, created1 = tracker.get_or_create_run("manual")
    assert created1 is True
    # A second call while one is live returns the same run, no duplicate.
    second, created2 = tracker.get_or_create_run("scheduled")
    assert created2 is False
    assert second is first
    # Once finished, a fresh run is created again.
    tracker.finish_run(first.run_id, [])
    third, created3 = tracker.get_or_create_run("manual")
    assert created3 is True
    assert third is not first


def test_get_or_create_run_replaces_stale_run(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    stale = tracker.create_run("manual")
    _make_stale(stale)
    # The stale run is reaped, so a brand-new run is created (not attached).
    fresh, created = tracker.get_or_create_run("manual")
    assert created is True
    assert fresh is not stale
    assert stale.status == "interrupted"


def test_get_run_log(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    # Write something via the logger
    test_logger = logging.getLogger("hebb.scheduler.consolidation_job")
    test_logger.setLevel(logging.DEBUG)
    test_logger.info("test log line from consolidation")
    tracker.finish_run(run.run_id, [])
    log = tracker.get_run_log(run.run_id)
    assert log is not None
    assert "test log line from consolidation" in log


def test_log_handler_attached_and_removed(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    test_logger = logging.getLogger("hebb.scheduler.consolidation_job")
    handler_count_before = len(test_logger.handlers)

    run = tracker.create_run("manual")
    assert len(test_logger.handlers) == handler_count_before + 1
    assert run.run_id in tracker._handlers

    tracker.finish_run(run.run_id, [])
    assert len(test_logger.handlers) == handler_count_before
    assert run.run_id not in tracker._handlers


def test_to_dict_fields(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    run = tracker.create_run("manual")
    d = run.to_dict()
    assert d["run_id"] == run.run_id
    assert d["trigger"] == "manual"
    assert d["status"] == "running"
    assert "started_at" in d
    assert "last_heartbeat" in d
    assert "log_file" in d


def test_get_run_unknown_returns_none(tmp_path: Path) -> None:
    tracker.init_tracker(tmp_path)
    assert tracker.get_run("nonexistent") is None
    assert tracker.get_run_log("nonexistent") is None
