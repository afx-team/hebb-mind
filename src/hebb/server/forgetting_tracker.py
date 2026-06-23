"""Lightweight run tracker for the forgetting sweep.

A sibling of :mod:`hebb.server.consolidation_tracker`, but deliberately simpler:
forgetting is a short, synchronous, atomic sweep (it runs to completion within a
single scheduler tick or one ``POST /forget`` call), so it needs none of the
consolidation tracker's per-run log files, heartbeat, or ``interrupted`` liveness
machinery. We only persist a small rolling history of "what each sweep did" —
when it ran, how it was triggered, how many memories it scanned and deleted —
so the console's 记忆遗忘 page can show real forgetting records.

The manifest (``logs/forgetting/manifest.json``) is the source of truth and is
written atomically; the in-memory registry is rebuilt from it at startup.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

RunStatus = Literal["done", "failed"]

MAX_RUNS = 20

_logs_dir: Path | None = None
_runs: dict[str, ForgettingRun] = {}


@dataclass
class ForgettingRun:
    """One forgetting sweep's outcome."""

    run_id: str
    trigger: str  # "scheduled" | "manual"
    status: RunStatus = "done"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    scanned: int = 0
    deleted: int = 0
    partitions_swept: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "scanned": self.scanned,
            "deleted": self.deleted,
            "partitions_swept": self.partitions_swept,
            "error": self.error,
        }


def init_forgetting_tracker(logs_dir: Path) -> None:
    """Initialise the tracker — call once during server lifespan startup."""
    global _logs_dir
    _logs_dir = logs_dir
    _logs_dir.mkdir(parents=True, exist_ok=True)
    _load_manifest()


def record_run(
    *,
    trigger: str,
    started_at: float,
    scanned: int,
    deleted: int,
    partitions_swept: int,
    status: RunStatus = "done",
    error: str | None = None,
) -> ForgettingRun:
    """Append a completed (or failed) forgetting sweep to the history."""
    run = ForgettingRun(
        run_id=uuid.uuid4().hex[:12],
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=time.time(),
        scanned=scanned,
        deleted=deleted,
        partitions_swept=partitions_swept,
        error=error,
    )
    _runs[run.run_id] = run
    _prune_old_runs()
    _save_manifest()
    return run


def list_runs() -> list[ForgettingRun]:
    """Return all forgetting runs, most-recent first."""
    return sorted(_runs.values(), key=lambda r: r.started_at, reverse=True)


# -- internal helpers --


def _prune_old_runs() -> None:
    ordered = sorted(_runs.values(), key=lambda r: r.started_at, reverse=True)
    for run in ordered[MAX_RUNS:]:
        _runs.pop(run.run_id, None)


def _manifest_path() -> Path:
    assert _logs_dir is not None
    return _logs_dir / "manifest.json"


def _save_manifest() -> None:
    # Best-effort: the manifest is a convenience record, not the source of truth
    # for the live session (the in-memory ``_runs`` registry serves list_runs).
    # An I/O error must never propagate out of record_run and abort a sweep.
    if _logs_dir is None:
        return
    path = _manifest_path()
    data = [r.to_dict() for r in sorted(_runs.values(), key=lambda r: r.started_at)]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".manifest.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except Exception:
        logger.warning("Failed to persist forgetting run manifest", exc_info=True)


def _load_manifest() -> None:
    global _runs
    if _logs_dir is None:
        return
    path = _manifest_path()
    if not path.is_file():
        _runs = {}
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _runs = {}
        return
    _runs = {}
    if not isinstance(data, list):
        return
    for entry in data:
        # Tolerate a malformed/partial entry rather than crashing startup
        # (init_forgetting_tracker runs unguarded in the server lifespan).
        try:
            run = ForgettingRun(
                run_id=entry["run_id"],
                trigger=entry.get("trigger", "scheduled"),
                status=entry.get("status", "done"),
                started_at=entry.get("started_at", 0.0),
                finished_at=entry.get("finished_at"),
                scanned=entry.get("scanned", 0),
                deleted=entry.get("deleted", 0),
                partitions_swept=entry.get("partitions_swept", 0),
                error=entry.get("error"),
            )
        except (KeyError, TypeError):
            continue
        _runs[run.run_id] = run
