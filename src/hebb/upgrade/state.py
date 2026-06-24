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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

STATE_FILENAME = "upgrade_state.json"

# How old an ``upgrade_in_progress`` attempt may be before it is treated as
# abandoned (helper killed before it could clear the flag). Comfortably longer
# than any real install + restart so a slow-but-live upgrade is never reset.
STALE_UPGRADE_SECONDS = 1800


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
    upgrade_helper_pid: int | None = None
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


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness check for ``pid``.

    On POSIX, ``os.kill(pid, 0)`` is the standard probe. On Windows it is NOT a
    probe: signal ``0`` is ``CTRL_C_EVENT``, so ``os.kill(pid, 0)`` would send a
    Ctrl+C to the process group (interrupting us). Windows uses the process
    handle instead.
    """
    if pid <= 0:
        return False
    if os.name == "nt":  # pragma: no cover - Windows-only
        return _win_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _win_pid_alive(pid: int) -> bool:  # pragma: no cover - Windows-only
    """Windows liveness probe via ``OpenProcess`` + ``GetExitCodeProcess``."""
    import ctypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    handle = kernel32.OpenProcess(process_query_limited_information, 0, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)) == 0:
            return True  # could not query — assume alive rather than reap a live run
        return code.value == still_active
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def reconcile_stale(home_dir: Path, max_age_seconds: int = STALE_UPGRADE_SECONDS) -> bool:
    """Clear a stuck ``upgrade_in_progress`` flag left by a dead helper.

    A helper that crashed before writing its final state would otherwise leave
    ``upgrade_in_progress=True`` forever, freezing the console banner and
    blocking ``/apply``. Resets the flag when the recorded helper PID is gone,
    or when the attempt started longer than ``max_age_seconds`` ago.

    Args:
        home_dir: Workspace root holding ``upgrade_state.json``.
        max_age_seconds: Age past which an in-progress attempt is abandoned.

    Returns:
        ``True`` if a stale flag was reset, ``False`` otherwise.
    """
    state = load(home_dir)
    if not state.upgrade_in_progress:
        return False

    stale = False
    if state.upgrade_helper_pid is not None and not _pid_alive(state.upgrade_helper_pid):
        stale = True
    started = state.last_upgrade.started_at if state.last_upgrade else None
    if not stale and started:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()
            stale = age > max_age_seconds
        except (ValueError, TypeError):
            stale = True
    elif not stale and started is None:
        # In progress with no record at all — there is nothing live to wait on.
        stale = True

    if not stale:
        return False

    state.upgrade_in_progress = False
    state.upgrade_helper_pid = None
    if state.last_upgrade and state.last_upgrade.status == "in_progress":
        state.last_upgrade.status = "failed"
        state.last_upgrade.finished_at = datetime.now(timezone.utc).isoformat()
        note = "interrupted — reset on restart"
        state.last_upgrade.log_tail = ((state.last_upgrade.log_tail or "") + "\n" + note).strip()
    save(home_dir, state)
    logger.info("Reset stale upgrade_in_progress flag (pid=%s)", state.upgrade_helper_pid)
    return True
