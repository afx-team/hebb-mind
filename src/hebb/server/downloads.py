"""In-process task table for long-running model downloads.

The web console polls these tasks while ``huggingface_hub.snapshot_download`` runs
in a worker thread; the tqdm callback (see ``hebb.embedding.progress``) mutates
the task in place. CPython dict / attribute writes are atomic enough for the
read-mostly polling pattern we need here, so no explicit locking is required.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["pending", "downloading", "verifying", "done", "failed"]


@dataclass
class DownloadTask:
    task_id: str
    model: str
    provider: str
    status: Status = "pending"
    bytes_done: int = 0
    bytes_total: int = 0
    current_file: str = ""
    dimension: int | None = None
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model": self.model,
            "provider": self.provider,
            "status": self.status,
            "bytes_done": self.bytes_done,
            "bytes_total": self.bytes_total,
            "current_file": self.current_file,
            "dimension": self.dimension,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


_tasks: dict[str, DownloadTask] = {}


def create_task(model: str, provider: str) -> DownloadTask:
    task = DownloadTask(task_id=uuid.uuid4().hex, model=model, provider=provider)
    _tasks[task.task_id] = task
    return task


def get_task(task_id: str) -> DownloadTask | None:
    return _tasks.get(task_id)


def update_task(task_id: str, **fields: Any) -> None:
    task = _tasks.get(task_id)
    if task is None:
        return
    for key, value in fields.items():
        setattr(task, key, value)
    if fields.get("status") in {"done", "failed"} and task.finished_at is None:
        task.finished_at = time.time()


def cleanup_old_tasks(max_age_seconds: int = 3600) -> None:
    """Drop finished tasks older than ``max_age_seconds`` to bound memory."""
    cutoff = time.time() - max_age_seconds
    for tid in list(_tasks.keys()):
        t = _tasks[tid]
        if t.finished_at is not None and t.finished_at < cutoff:
            _tasks.pop(tid, None)
