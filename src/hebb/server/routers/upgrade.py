"""Upgrade endpoints — read state, force a check, apply, dismiss.

All under ``/api/v1/admin/upgrade``:

* ``GET   /``       — persisted state + ``mode`` + detected install method.
* ``POST  /check``  — force a PyPI check now (bypasses the cron schedule).
* ``POST  /apply``  — spawn the detached upgrade helper.
* ``POST  /dismiss``— hide the banner until a newer version appears.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from hebb.config.settings import Settings
from hebb.server.dependencies import get_settings
from hebb.upgrade import installer
from hebb.upgrade import state as upgrade_state
from hebb.upgrade.checker import run_check
from hebb.upgrade.helper import spawn_detached

logger = logging.getLogger(__name__)

router = APIRouter()


def _state_payload(settings: Settings) -> dict[str, Any]:
    """Build the JSON response shape: state + mode + detected install method."""
    if settings.home_dir is None:
        raise HTTPException(status_code=500, detail="home_dir not resolved")
    state = upgrade_state.load(settings.home_dir)
    data = state.model_dump(mode="json")
    data["mode"] = settings.auto_upgrade_mode
    cmd = installer.build_command()
    data["method"] = cmd.method
    data["auto_upgradable"] = cmd.auto_upgradable
    data["refusal_reason"] = cmd.refusal_reason
    return data


def _spawn_helper(settings: Settings, method: str) -> int:
    """Spawn the detached upgrade helper, returning its PID."""
    return spawn_detached(
        home_dir=settings.home_dir,  # type: ignore[arg-type]  # checked non-None by caller
        port=settings.port,
        grace=settings.upgrade_grace_seconds,
        method=method,
        parent_pid=os.getpid(),
    )


@router.get("")
async def get_upgrade_state(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Return persisted upgrade check state + current ``auto_upgrade_mode``."""
    return _state_payload(settings)


@router.post("/check")
async def force_check(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Force a PyPI check now (bypasses the cron schedule)."""
    if settings.auto_upgrade_mode == "off":
        raise HTTPException(status_code=409, detail="Upgrade checks are disabled (auto_upgrade_mode=off)")
    if settings.home_dir is None:
        raise HTTPException(status_code=500, detail="home_dir not resolved")
    await run_check(settings.home_dir)
    return _state_payload(settings)


@router.post("/apply")
async def apply_upgrade(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Spawn the detached upgrade helper after validating it is safe to run.

    Refuses when: checks are disabled (``mode=off``), no newer version is
    available, an upgrade is already in progress, or the install method is not
    auto-upgradable (editable / system-managed).
    """
    if settings.auto_upgrade_mode == "off":
        raise HTTPException(status_code=409, detail="Upgrades are disabled (auto_upgrade_mode=off)")
    if settings.home_dir is None:
        raise HTTPException(status_code=500, detail="home_dir not resolved")

    # Clear a flag left stuck by a helper that died before reporting, so a real
    # retry isn't blocked forever (no-op for a genuinely live upgrade).
    upgrade_state.reconcile_stale(settings.home_dir)

    state = upgrade_state.load(settings.home_dir)
    if state.upgrade_in_progress:
        raise HTTPException(status_code=409, detail="An upgrade is already in progress")
    if not state.available:
        raise HTTPException(status_code=409, detail="No upgrade available")

    cmd = installer.build_command()
    if not cmd.auto_upgradable:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot auto-upgrade: {cmd.refusal_reason}",
        )

    # Close the double-click window before spawning. This handler is async with
    # no await before the spawn, so the event loop serializes concurrent /apply
    # calls — the second one observes upgrade_in_progress and is refused above.
    upgrade_state.update(settings.home_dir, upgrade_in_progress=True)
    try:
        pid = _spawn_helper(settings, cmd.method)
    except Exception as exc:
        # Spawn failed — roll back the in-progress flag so the banner recovers.
        upgrade_state.update(settings.home_dir, upgrade_in_progress=False)
        logger.exception("Failed to spawn upgrade helper")
        raise HTTPException(status_code=500, detail=f"Failed to start upgrade: {exc}")

    upgrade_state.update(settings.home_dir, upgrade_helper_pid=pid)
    payload = _state_payload(settings)
    payload["spawned"] = True
    return payload


@router.post("/dismiss")
async def dismiss_upgrade(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Hide the banner for the current latest version (until a newer one appears)."""
    if settings.home_dir is None:
        raise HTTPException(status_code=500, detail="home_dir not resolved")
    state = upgrade_state.load(settings.home_dir)
    if state.latest_version:
        upgrade_state.update(settings.home_dir, dismissed_for_version=state.latest_version)
    return _state_payload(settings)
