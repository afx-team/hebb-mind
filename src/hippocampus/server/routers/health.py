"""Health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hippocampus import __version__
from hippocampus.scheduler.manager import SchedulerManager
from hippocampus.server.dependencies import get_scheduler

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/status")
async def status(scheduler: SchedulerManager = Depends(get_scheduler)):
    return {
        "version": __version__,
        "scheduler": scheduler.get_status(),
    }
