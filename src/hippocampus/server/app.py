"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from hippocampus import __version__
from hippocampus.config.loader import load_settings
from hippocampus.embedding.local import LocalEmbedder, NoopEmbedder
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.retrieval.searcher import MemorySearcher
from hippocampus.scheduler.manager import SchedulerManager
from hippocampus.storage.factory import create_stores

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, storage, embedder, graph, scheduler. Shutdown: cleanup."""
    settings = load_settings()
    app.state.settings = settings

    # Storage (backend selected by settings.storage_type)
    ctx = await create_stores(settings)
    app.state.memory_store = ctx.memory_store
    app.state.partition_store = ctx.partition_store

    # Ensure default partitions
    await ctx.partition_store.ensure_defaults()

    # Embedder (optional — can be disabled via config or fails gracefully)
    if not settings.embedding_enabled:
        logger.info("Embedding disabled by config, vector search unavailable")
        embedder = NoopEmbedder(settings.embedding_dim)
    else:
        try:
            logger.info("Loading embedding model: %s", settings.embedding_model)
            embedder = LocalEmbedder(settings.embedding_model)
        except Exception:
            logger.warning("Failed to load embedding model, vector search disabled")
            embedder = NoopEmbedder(settings.embedding_dim)
    app.state.embedder = embedder

    # Knowledge graph
    kg = KnowledgeGraph(Path(settings.kg_path))
    app.state.knowledge_graph = kg

    # Searcher (with graph for hybrid retrieval)
    searcher = MemorySearcher(store=ctx.memory_store, embedder=embedder, graph=kg)
    app.state.searcher = searcher

    # Scheduler
    scheduler = SchedulerManager(
        settings=settings,
        memory_store=ctx.memory_store,
        partition_store=ctx.partition_store,
        knowledge_graph=kg,
        embedder=embedder,
    )
    app.state.scheduler = scheduler
    scheduler.start()

    logger.info(
        "Hippocampus v%s started on %s:%d [%s]", __version__, settings.host, settings.port, settings.storage_type
    )

    yield

    # Shutdown
    scheduler.shutdown()
    kg.save()
    await ctx.close()
    logger.info("Hippocampus shut down")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Hippocampus",
        description="Neuroscience-inspired memory framework for AI agents",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from hippocampus.server.routers import admin, config, graph, health, memories, partitions, search

    app.include_router(health.router, tags=["health"])
    app.include_router(partitions.router, prefix="/api/v1", tags=["partitions"])
    app.include_router(memories.router, prefix="/api/v1", tags=["memories"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(config.router, prefix="/api/v1/admin", tags=["config"])

    # Mount static web console (after API routers so they take precedence)
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
