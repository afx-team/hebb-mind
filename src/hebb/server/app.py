"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from hebb import __version__
from hebb.config.loader import load_settings
from hebb.embedding.factory import create_embedder
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.retrieval.rerank import create_reranker
from hebb.retrieval.searcher import MemorySearcher
from hebb.scheduler.manager import SchedulerManager
from hebb.server.auth import AntiCsrfMiddleware
from hebb.storage.factory import create_stores

logger = logging.getLogger(__name__)


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that asks browsers to revalidate before reusing a cached asset.

    The console is a module-graph SPA: ``app.js`` statically imports component
    modules by path. If a browser keeps a stale ``app.js`` after an upgrade, it
    can try to import a module the new build deleted — the import 404s and the
    whole console fails to boot (buttons render but never wire up). Sending
    ``Cache-Control: no-cache`` forces a conditional revalidation on every load,
    so an upgraded build is always picked up (304 when unchanged — negligible
    cost on a localhost console).
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: load config, storage, embedder, graph, scheduler. Shutdown: cleanup."""
    settings = load_settings()
    # load_settings() always resolves the workspace root (loader.py), so
    # home_dir is non-None here even though the field type allows None.
    assert settings.home_dir is not None
    app.state.settings = settings

    # A previous upgrade helper may have been killed before clearing its flag
    # (or the OS supervisor respawned the old daemon mid-upgrade). Clear any
    # stale ``upgrade_in_progress`` now so the console banner isn't frozen.
    from hebb.upgrade import state as upgrade_state

    upgrade_state.reconcile_stale(settings.home_dir)

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

    # Consolidation run tracker (per-run log files + manifest). Reaps any run
    # left ``running`` by a previous process (crash / shutdown / sleep) to
    # ``interrupted``; a non-zero count means a run did not finish.
    from hebb.constants import PartitionType
    from hebb.server.consolidation_tracker import init_tracker
    from hebb.server.forgetting_tracker import init_forgetting_tracker

    interrupted = init_tracker(Path(settings.home_dir) / "logs" / "consolidation")
    # Forgetting run history (records for the console's 记忆遗忘 page).
    init_forgetting_tracker(Path(settings.home_dir) / "logs" / "forgetting")

    # Resume an interrupted run: if there are still working memories waiting and
    # an LLM is configured, schedule a catch-up so the inbox is consolidated on
    # the next boot rather than waiting for the daily cron ("下次继续").
    if interrupted and settings.llm_model:
        partitions = await ctx.partition_store.list()
        hippo = next(
            (p for p in partitions if p.id == PartitionType.HIPPOCAMPUS.value),
            None,
        )
        pending = hippo.memory_count if hippo else 0
        if pending > 0:
            logger.info(
                "Detected %d interrupted consolidation run(s) with %d pending memories; scheduling catch-up",
                interrupted,
                pending,
            )
            scheduler.schedule_catchup()

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
    # Release embedder resources (e.g. the async HTTP client of an API/custom
    # embedder). aclose() is added by the embedding layer (INT-3); guard with
    # hasattr so embedders that don't define it (local sentence-transformers)
    # are unaffected.
    if hasattr(embedder, "aclose"):
        await embedder.aclose()
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

    # CORS is restricted to the console's own loopback origins, and credentials
    # are disabled — the console is served same-origin from this process and
    # uses no cookies, so the insecure ``allow_origins=["*"] + credentials``
    # combo (which let any webpage read responses) is gone. Origins are derived
    # from the configured port at startup.
    settings = load_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Anti-CSRF / drive-by guard (INT-1): reject cross-origin browser requests to
    # state-changing or secret-exposing routes. Applied globally so every router
    # is covered without per-route auth.
    app.add_middleware(AntiCsrfMiddleware)

    from hebb.server.routers import (
        admin,
        agent_sync,
        claude_memory,
        config,
        forgetting,
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
    app.include_router(agent_sync.router, prefix="/api/v1/agent-sync", tags=["agent-sync"])
    app.include_router(claude_memory.router, prefix="/api/v1/claude-memory", tags=["claude-memory"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(config.router, prefix="/api/v1/admin", tags=["config"])
    app.include_router(forgetting.router, prefix="/api/v1/admin", tags=["forgetting"])
    app.include_router(upgrade.router, prefix="/api/v1/admin/upgrade", tags=["upgrade"])

    # Mount static web console (after API routers so they take precedence).
    # Served with ``Cache-Control: no-cache`` so the browser always revalidates:
    # an upgrade must never leave a stale ``app.js`` cached that still imports
    # modules a newer build has removed (the cached module graph 404s and the
    # SPA fails to boot). Revalidation is a cheap conditional request on the
    # local console and returns 304 when nothing changed.
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", NoCacheStaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
