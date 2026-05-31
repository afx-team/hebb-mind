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
from hebb.retrieval.rerank import create_reranker
from hebb.retrieval.searcher import MemorySearcher
from hebb.scheduler.manager import SchedulerManager
from hebb.storage.factory import create_stores

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: load config, storage, embedder, graph, scheduler. Shutdown: cleanup."""
    settings = load_settings()
    app.state.settings = settings

    # Embedder FIRST — the vec0 virtual table is created with a fixed
    # ``float[N]`` width, so the storage layer must know the real
    # embedding dimension before it builds the schema. Constructing the
    # embedder reports its true dimension (which can differ from the
    # configured ``embedding_dim``, e.g. when the model is overridden at
    # runtime); we pin settings to it before create_stores runs.
    embedder = await create_embedder(settings)
    settings.embedding_dim = embedder.dimension
    app.state.embedder = embedder

    # Storage (backend selected by settings.storage_type) — vec0 table
    # now sized to the embedder's actual dimension.
    ctx = await create_stores(settings)
    app.state.memory_store = ctx.memory_store
    app.state.partition_store = ctx.partition_store

    # Ensure default partitions
    await ctx.partition_store.ensure_defaults()

    # Knowledge graph
    kg = KnowledgeGraph(Path(settings.kg_path))  # kg_path already resolved to absolute
    app.state.knowledge_graph = kg

    # Optional cross-encoder reranker (None when settings.rerank_enabled=False).
    reranker = create_reranker(settings)
    app.state.reranker = reranker

    # Searcher (with graph for hybrid retrieval, optional rerank pass,
    # plus per-pipeline-stage toggles for A/B ablation).
    searcher = MemorySearcher(
        store=ctx.memory_store,
        embedder=embedder,
        graph=kg,
        reranker=reranker,
        vector_search_enabled=settings.vector_search_enabled,
        keyword_search_enabled=settings.keyword_search_enabled,
        graph_search_enabled=settings.graph_search_enabled,
        lexical_boost_enabled=settings.lexical_boost_enabled,
        temporal_boost_enabled=settings.temporal_boost_enabled,
        graph_expansion_enabled=settings.graph_expansion_enabled,
        keyword_blend_enabled=settings.keyword_blend_enabled,
    )
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

    from hebb.server.routers import (
        admin,
        claude_memory,
        config,
        graph,
        health,
        memories,
        partitions,
        search,
        upgrade,
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(partitions.router, prefix="/api/v1", tags=["partitions"])
    app.include_router(memories.router, prefix="/api/v1", tags=["memories"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
    app.include_router(claude_memory.router, prefix="/api/v1/claude-memory", tags=["claude-memory"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(config.router, prefix="/api/v1/admin", tags=["config"])
    app.include_router(upgrade.router, prefix="/api/v1/admin/upgrade", tags=["upgrade"])

    # Mount static web console (after API routers so they take precedence)
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
