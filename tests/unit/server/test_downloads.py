"""Tests for the in-process download task table."""

from __future__ import annotations

import time

from hebb.server import downloads


def setup_function() -> None:
    downloads._tasks.clear()


def test_create_assigns_unique_ids() -> None:
    a = downloads.create_task("model-a", "local")
    b = downloads.create_task("model-b", "local")
    assert a.task_id != b.task_id
    assert downloads.get_task(a.task_id) is a
    assert downloads.get_task(b.task_id) is b


def test_create_initial_state() -> None:
    task = downloads.create_task("BAAI/bge-m3", "local")
    assert task.status == "pending"
    assert task.bytes_done == 0
    assert task.bytes_total == 0
    assert task.dimension is None
    assert task.error is None
    assert task.finished_at is None


def test_update_writes_fields() -> None:
    task = downloads.create_task("m", "local")
    downloads.update_task(task.task_id, status="downloading", bytes_done=128, bytes_total=1024)
    again = downloads.get_task(task.task_id)
    assert again is not None
    assert again.status == "downloading"
    assert again.bytes_done == 128
    assert again.bytes_total == 1024
    assert again.finished_at is None


def test_terminal_status_sets_finished_at() -> None:
    task = downloads.create_task("m", "local")
    downloads.update_task(task.task_id, status="done", dimension=1024)
    assert downloads.get_task(task.task_id).finished_at is not None  # type: ignore[union-attr]

    task2 = downloads.create_task("m2", "local")
    downloads.update_task(task2.task_id, status="failed", error="boom")
    assert downloads.get_task(task2.task_id).finished_at is not None  # type: ignore[union-attr]


def test_update_unknown_id_is_noop() -> None:
    # Must not raise — polling endpoints rely on this for races.
    downloads.update_task("does-not-exist", status="done")


def test_cleanup_drops_old_finished_tasks() -> None:
    old = downloads.create_task("old", "local")
    fresh = downloads.create_task("fresh", "local")
    downloads.update_task(old.task_id, status="done")
    downloads.update_task(fresh.task_id, status="done")
    # Backdate `old` past the retention window.
    downloads._tasks[old.task_id].finished_at = time.time() - 7200

    downloads.cleanup_old_tasks(max_age_seconds=3600)
    assert downloads.get_task(old.task_id) is None
    assert downloads.get_task(fresh.task_id) is not None


def test_cleanup_does_not_drop_in_flight_tasks() -> None:
    inflight = downloads.create_task("inflight", "local")
    downloads.update_task(inflight.task_id, status="downloading")
    downloads.cleanup_old_tasks(max_age_seconds=0)
    assert downloads.get_task(inflight.task_id) is not None


def test_to_dict_round_trip() -> None:
    task = downloads.create_task("m", "local")
    downloads.update_task(task.task_id, status="done", dimension=384, bytes_done=10, bytes_total=10)
    d = downloads.get_task(task.task_id).to_dict()  # type: ignore[union-attr]
    assert d["status"] == "done"
    assert d["dimension"] == 384
    assert d["bytes_done"] == 10
    assert d["bytes_total"] == 10
    assert "task_id" in d
    assert "started_at" in d
