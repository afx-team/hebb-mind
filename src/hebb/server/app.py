"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from hebb import __version__
from hebb.config.loader import load_settings
from hebb.embedding.factory import create_embedder
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.retrieval.searcher import MemorySearcher
from hebb.scheduler.manager import SchedulerManager
from hebb.storage.factory import create_stores

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: load config, storage, embedder, graph, scheduler. Shutdown: cleanup."""
    settings = load_settings()
    app.state.settings = settings

    # Storage (backend selected by settings.storage_type)
    ctx = await create_stores(settings)
    app.state.memory_store = ctx.memory_store
    app.state.partition_store = ctx.partition_store

    # Ensure default partitions
    await ctx.partition_store.ensure_defaults()

    # Embedder (local or API, selected by config)
    embedder = await create_embedder(settings)
    settings.embedding_dim = embedder.dimension
    app.state.embedder = embedder

    # Knowledge graph
    kg = KnowledgeGraph(Path(settings.kg_path))  # kg_path already resolved to absolute
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
        "Hebb Mind v%s started on %s:%d [%s] workspace=%s",
        __version__,
        settings.host,
        settings.port,
        settings.storage_type,
        settings.home_dir,
    )

    yield

    # Shutdown
    scheduler.shutdown()
    kg.save()
    await ctx.close()
    logger.info("Hebb Mind shut down")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="HebbMind",
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

    from hebb.server.routers import admin, config, graph, health, memories, partitions, search

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
