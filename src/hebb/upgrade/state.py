"""Upgrade state file — ``~/.hebb/upgrade_state.json``.

Owned by the daemon's scheduler job (for read-after-check) and by the
detached upgrade helper (for write-during-upgrade). Atomic write via
``tempfile`` + ``os.replace`` so concurrent readers never see a partial
JSON document.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

STATE_FILENAME = "upgrade_state.json"


class LastUpgrade(BaseModel):
    """Record of the most recent upgrade attempt."""

    from_version: str
    to_version: str
    started_at: str
    finished_at: str | None = None
    status: str  # "in_progress" | "success" | "failed"
    method: str  # "pip" | "pipx" | "uv-tool" | "editable"
    log_tail: str | None = None


class UpgradeState(BaseModel):
    """Persisted upgrade-check / upgrade-attempt state."""

    current_version: str = ""
    latest_version: str | None = None
    checked_at: str | None = None
    available: bool = False
    notified_for_version: str | None = None
    dismissed_for_version: str | None = None
    last_check_error: str | None = None
    upgrade_in_progress: bool = False
    last_upgrade: LastUpgrade | None = None


def state_path(home_dir: Path) -> Path:
    """Path to the upgrade state file inside ``home_dir``."""
    return home_dir / STATE_FILENAME


def load(home_dir: Path) -> UpgradeState:
    """Load state from disk. Returns default state when missing or corrupt."""
    path = state_path(home_dir)
    if not path.is_file():
        return UpgradeState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("upgrade_state.json unreadable (%s); returning default state", exc)
        return UpgradeState()
    try:
        return UpgradeState.model_validate(raw)
    except Exception as exc:
        logger.warning("upgrade_state.json schema mismatch (%s); returning default state", exc)
        return UpgradeState()


def save(home_dir: Path, state: UpgradeState) -> Path:
    """Atomically write state to disk. Returns the path written."""
    path = state_path(home_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = state.model_dump(mode="json", exclude_none=False)
    tmp_fd, tmp_path_str = tempfile.mkstemp(prefix=".upgrade_state.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return path


def update(home_dir: Path, **changes: Any) -> UpgradeState:
    """Read-modify-write convenience: load, apply ``changes``, save, return."""
    current = load(home_dir)
    merged = current.model_dump()
    merged.update(changes)
    new_state = UpgradeState.model_validate(merged)
    save(home_dir, new_state)
    return new_state
