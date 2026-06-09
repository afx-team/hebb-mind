"""In-process run tracker for consolidation jobs with per-run log files.

Follows the same module-level registry pattern as ``downloads.py``.
Each run gets a dedicated log file under ``<workdir>/logs/consolidation/``;
a JSON manifest persists run metadata across server restarts.

Liveness model (the "working" state, avoiding races and stuck runs)
-------------------------------------------------------------------
A consolidation run is the *single* working state: only one may be ``running``
at a time (callers gate on :func:`get_or_create_run` / the scheduler's lock).

A long-lived daemon cannot rely on a process restart to clean up a run that
stalls or is interrupted (network loss, laptop sleep, ``kill -9``). So every
run carries a ``last_heartbeat`` that the executor bumps periodically; a run
whose heartbeat (or log-file mtime) has gone silent for longer than
``STALE_AFTER_SECONDS`` is considered dead and is *reaped* — flipped to the
``"interrupted"`` status — on the next read (:func:`get_current_run`,
:func:`list_runs`, :func:`get_run`) and at startup (:func:`init_tracker`).
This keeps the manifest/log files the source of truth ("通过 logs 文件判断"):
a reader never sees a permanently-stuck ``running`` run, and a fresh run can
always start to *continue* the unprocessed inbox ("下次继续，而不是卡住").

``"interrupted"`` is kept distinct from ``"failed"``: the former means the run
did not complete (stopped/stalled) and will be resumed automatically; the
latter means it ran to completion but raised (e.g. an LLM error).
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

RunStatus = Literal["running", "done", "failed", "interrupted"]

_RUN_LOGGERS = [
    "hebb.scheduler.consolidation_job",
    "hebb.agents.consolidation_agent",
]

MAX_RUNS = 20

# How often the executor bumps a run's heartbeat, and how long a ``running``
# run may go silent before it is treated as interrupted. STALE_AFTER is set
# generously above the per-request LLM timeout (120s) so a normal in-flight
# call — during which the independent heartbeat task keeps ticking — is never
# falsely reaped, while a genuine hang is reclaimed within a few minutes.
HEARTBEAT_INTERVAL_SECONDS = 20.0
STALE_AFTER_SECONDS = 180.0

_INTERRUPTED_MESSAGE = (
    "interrupted — the run did not complete (service stopped, system sleep, or "
    "network loss); remaining memories will be consolidated on the next run"
)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s — %(message)s"

_logs_dir: Path | None = None
_runs: dict[str, ConsolidationRun] = {}
_handlers: dict[str, logging.FileHandler] = {}


@dataclass
class ConsolidationRun:
    run_id: str
    trigger: str
    status: RunStatus = "running"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    last_heartbeat: float = field(default_factory=time.time)
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    log_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_heartbeat": self.last_heartbeat,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "errors": self.errors,
            "log_file": self.log_file,
        }


def init_tracker(logs_dir: Path) -> int:
    """Initialise the tracker — call once during server lifespan startup.

    Any run still marked ``running`` in the persisted manifest belongs to a
    previous process that is now gone, so it is reaped to ``"interrupted"``.

    Returns:
        The number of interrupted (reaped) runs — the caller uses a non-zero
        count to schedule a catch-up consolidation that resumes the inbox.
    """
    global _logs_dir
    _logs_dir = logs_dir
    _logs_dir.mkdir(parents=True, exist_ok=True)
    _load_manifest()
    reaped = 0
    for run in _runs.values():
        if run.status == "running":
            run.status = "interrupted"
            run.finished_at = run.finished_at or time.time()
            if not run.errors:
                run.errors = [{"memory_id": "", "error": _INTERRUPTED_MESSAGE}]
            reaped += 1
    if _runs:
        _save_manifest()
    return reaped


def create_run(trigger: str) -> ConsolidationRun:
    """Create a new tracked consolidation run and attach log handlers."""
    run_id = uuid.uuid4().hex[:12]
    log_filename = f"run-{run_id}.log"
    now = time.time()
    run = ConsolidationRun(
        run_id=run_id,
        trigger=trigger,
        started_at=now,
        last_heartbeat=now,
        log_file=log_filename,
    )
    _runs[run_id] = run
    _prune_old_runs()
    _save_manifest()
    _attach_log_handler(run_id, log_filename)
    return run


def get_or_create_run(trigger: str) -> tuple[ConsolidationRun, bool]:
    """Return the live run if one exists, else create a new one.

    Gates the "single working state": callers use the ``created`` flag to avoid
    starting a duplicate run (UI double-click, a manual trigger landing on top
    of the daily cron). Runs entirely synchronously — no ``await`` between the
    liveness check and ``create_run`` — so it is atomic on the event loop.

    Returns:
        ``(run, created)`` where ``created`` is ``False`` when an in-progress
        run was returned instead of a new one.
    """
    existing = get_current_run()
    if existing is not None:
        return existing, False
    return create_run(trigger), True


def heartbeat(run_id: str) -> None:
    """Mark a running run as still alive. No-op for unknown/finished runs."""
    run = _runs.get(run_id)
    if run is None or run.status != "running":
        return
    run.last_heartbeat = time.time()
    _save_manifest()


def finish_run(
    run_id: str,
    results: list[Any],
) -> None:
    """Mark a run as done and populate its counters from results."""
    run = _runs.get(run_id)
    if run is None:
        return
    run.status = "done"
    run.finished_at = time.time()
    run.processed = len(results)
    run.succeeded = sum(1 for r in results if r.success)
    failures = [{"memory_id": r.original_memory_id, "error": r.error or "unknown"} for r in results if not r.success]
    run.failed = len(failures)
    run.errors = failures
    _detach_log_handler(run_id)
    _save_manifest()


def fail_run(run_id: str, error_msg: str) -> None:
    """Mark a run as failed with an error message."""
    run = _runs.get(run_id)
    if run is None:
        return
    run.status = "failed"
    run.finished_at = time.time()
    run.errors = [{"memory_id": "", "error": error_msg}]
    _detach_log_handler(run_id)
    _save_manifest()


def get_run(run_id: str) -> ConsolidationRun | None:
    _reap_stale()
    return _runs.get(run_id)


def get_current_run() -> ConsolidationRun | None:
    """Return the in-progress run, if any — reaping any stalled run first."""
    _reap_stale()
    for run in _runs.values():
        if run.status == "running":
            return run
    return None


def list_runs() -> list[ConsolidationRun]:
    """Return all runs, most-recent first."""
    _reap_stale()
    return sorted(_runs.values(), key=lambda r: r.started_at, reverse=True)


def get_run_log(run_id: str) -> str | None:
    """Read the log file content for a run."""
    run = _runs.get(run_id)
    if run is None or _logs_dir is None:
        return None
    log_path = _logs_dir / run.log_file
    if not log_path.is_file():
        return ""
    return log_path.read_text(encoding="utf-8", errors="replace")


# -- internal helpers --


def _reap_stale() -> int:
    """Flip any ``running`` run whose heartbeat has gone silent to interrupted.

    Liveness is ``max(last_heartbeat, log-file mtime)`` so a run that is still
    actively writing logs counts as alive even if the heartbeat task lags. The
    active run's heartbeat keeps it fresh; only a genuinely stalled/abandoned
    run crosses ``STALE_AFTER_SECONDS``. Mutating on read is intentional — it
    is the self-healing that prevents a permanently-stuck ``running`` state.
    """
    now = time.time()
    reaped = 0
    for run in _runs.values():
        if run.status != "running":
            continue
        liveness = max(run.last_heartbeat, _log_mtime(run))
        if now - liveness > STALE_AFTER_SECONDS:
            run.status = "interrupted"
            run.finished_at = now
            if not run.errors:
                run.errors = [{"memory_id": "", "error": _INTERRUPTED_MESSAGE}]
            _detach_log_handler(run.run_id)
            reaped += 1
    if reaped:
        _save_manifest()
    return reaped


def _log_mtime(run: ConsolidationRun) -> float:
    if _logs_dir is None or not run.log_file:
        return 0.0
    try:
        return (_logs_dir / run.log_file).stat().st_mtime
    except OSError:
        return 0.0


def _attach_log_handler(run_id: str, log_filename: str) -> None:
    if _logs_dir is None:
        return
    log_path = _logs_dir / log_filename
    handler = logging.FileHandler(str(log_path), encoding="utf-8")
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.setLevel(logging.DEBUG)
    _handlers[run_id] = handler
    for name in _RUN_LOGGERS:
        logging.getLogger(name).addHandler(handler)


def _detach_log_handler(run_id: str) -> None:
    handler = _handlers.pop(run_id, None)
    if handler is None:
        return
    for name in _RUN_LOGGERS:
        logging.getLogger(name).removeHandler(handler)
    handler.close()


def _prune_old_runs() -> None:
    ordered = sorted(_runs.values(), key=lambda r: r.started_at, reverse=True)
    to_remove = ordered[MAX_RUNS:]
    for run in to_remove:
        if _logs_dir is not None:
            log_path = _logs_dir / run.log_file
            log_path.unlink(missing_ok=True)
        _runs.pop(run.run_id, None)


def _manifest_path() -> Path:
    assert _logs_dir is not None
    return _logs_dir / "manifest.json"


def _save_manifest() -> None:
    if _logs_dir is None:
        return
    path = _manifest_path()
    data = [r.to_dict() for r in sorted(_runs.values(), key=lambda r: r.started_at)]
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
    for entry in data:
        started_at = entry.get("started_at", 0.0)
        run = ConsolidationRun(
            run_id=entry["run_id"],
            trigger=entry.get("trigger", "manual"),
            status=entry.get("status", "done"),
            started_at=started_at,
            finished_at=entry.get("finished_at"),
            last_heartbeat=entry.get("last_heartbeat", started_at),
            processed=entry.get("processed", 0),
            succeeded=entry.get("succeeded", 0),
            failed=entry.get("failed", 0),
            errors=entry.get("errors", []),
            log_file=entry.get("log_file", ""),
        )
        _runs[run.run_id] = run
