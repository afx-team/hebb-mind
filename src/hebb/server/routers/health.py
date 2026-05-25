"""Health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hebb import __version__
from hebb.config.settings import Settings
from hebb.embedding.base import EmbeddingProvider
from hebb.embedding.local import NoopEmbedder
from hebb.scheduler.manager import SchedulerManager
from hebb.server.dependencies import get_embedder, get_scheduler, get_settings

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/status")
async def status(
    scheduler: SchedulerManager = Depends(get_scheduler),
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingProvider = Depends(get_embedder),
):
    return {
        "version": __version__,
        "scheduler": scheduler.get_status(),
        "embedding": {
            "enabled": settings.embedding_enabled,
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimension": embedder.dimension,
            "available": not isinstance(embedder, NoopEmbedder),
        },
    }
