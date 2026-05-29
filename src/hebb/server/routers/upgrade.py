"""Upgrade endpoints — read state, force a PyPI check.

PR-1 surface: ``GET /api/v1/admin/upgrade`` (read state) and
``POST /api/v1/admin/upgrade/check`` (force a check now). The ``apply`` and
``dismiss`` endpoints land in PR-2.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from hebb.config.settings import Settings
from hebb.server.dependencies import get_settings
from hebb.upgrade import state as upgrade_state
from hebb.upgrade.checker import run_check

logger = logging.getLogger(__name__)

router = APIRouter()


def _state_payload(settings: Settings) -> dict[str, Any]:
    """Build the JSON response shape for ``GET /upgrade``."""
    if settings.home_dir is None:
        raise HTTPException(status_code=500, detail="home_dir not resolved")
    state = upgrade_state.load(settings.home_dir)
    data = state.model_dump(mode="json")
    data["mode"] = settings.auto_upgrade_mode
    return data


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
