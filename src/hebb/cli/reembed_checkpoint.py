"""On-disk checkpoint for ``hebb memory reembed``.

A reembed run can be interrupted at any time (Ctrl-C, lid close, process kill).
We persist a small JSON file next to ``hebb.json`` so the next invocation can
pick up where the previous one stopped, *as long as the target embedder
hasn't changed since*.

File layout::

    {
      "schema_version": 1,
      "target_model": "BAAI/bge-m3",
      "target_dim": 1024,
      "partition_id": null,
      "started_at": "2026-05-26T14:08:31Z",
      "updated_at": "2026-05-26T14:09:02Z",
      "total": 8762,
      "pending_ids": ["...", "..."]
    }

Identity = (``target_model``, ``target_dim``, ``partition_id``). If the live
``Settings`` values differ from what the checkpoint records, the user has
moved on to a different migration — we drop the stale checkpoint and start
fresh, exactly as the user requested.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHECKPOINT_FILENAME = "reembed.checkpoint.json"
SCHEMA_VERSION = 1


@dataclass
class ReembedCheckpoint:
    target_model: str
    target_dim: int
    partition_id: str | None
    total: int
    pending_ids: list[str]
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    schema_version: int = SCHEMA_VERSION

    def matches(self, *, model: str, dim: int, partition_id: str | None) -> bool:
        return self.target_model == model and self.target_dim == dim and self.partition_id == partition_id

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> ReembedCheckpoint:
        data = json.loads(raw)
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Unsupported checkpoint schema_version={data.get('schema_version')!r}")
        return cls(
            target_model=data["target_model"],
            target_dim=int(data["target_dim"]),
            partition_id=data.get("partition_id"),
            total=int(data["total"]),
            pending_ids=list(data["pending_ids"]),
            started_at=data["started_at"],
            updated_at=data["updated_at"],
            schema_version=int(data["schema_version"]),
        )


def checkpoint_path(workspace: Path | None) -> Path | None:
    if workspace is None:
        return None
    return Path(workspace) / CHECKPOINT_FILENAME


def load(workspace: Path | None) -> ReembedCheckpoint | None:
    path = checkpoint_path(workspace)
    if path is None or not path.is_file():
        return None
    try:
        return ReembedCheckpoint.from_json(path.read_text(encoding="utf-8"))
    except (ValueError, KeyError, json.JSONDecodeError):
        # Corrupt or unknown-schema checkpoint — treat as absent. Don't delete
        # silently; the caller decides whether to overwrite.
        return None


def save(cp: ReembedCheckpoint, workspace: Path | None) -> None:
    path = checkpoint_path(workspace)
    if path is None:
        return
    cp.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = cp.to_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: tmp + fsync + rename so we never leave a half-written
    # JSON if the process dies during save itself.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(payload)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def delete(workspace: Path | None) -> bool:
    path = checkpoint_path(workspace)
    if path is None or not path.is_file():
        return False
    path.unlink()
    return True


def summarize(cp: ReembedCheckpoint) -> dict[str, Any]:
    """Compact human-friendly summary for CLI output."""
    done = cp.total - len(cp.pending_ids)
    pct = (100.0 * done / cp.total) if cp.total else 0.0
    return {
        "target_model": cp.target_model,
        "target_dim": cp.target_dim,
        "partition_id": cp.partition_id,
        "started_at": cp.started_at,
        "updated_at": cp.updated_at,
        "done": done,
        "total": cp.total,
        "pct": pct,
    }
