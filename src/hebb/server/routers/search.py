"""Memory search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hebb.config.settings import Settings
from hebb.models.memory import MemoryQuery, SearchResponse
from hebb.retrieval.searcher import MemorySearcher
from hebb.server.dependencies import get_memory_store, get_searcher, get_settings
from hebb.storage.base import MemoryStore

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_memories(
    query: MemoryQuery,
    searcher: MemorySearcher = Depends(get_searcher),
    settings: Settings = Depends(get_settings),
    store: MemoryStore = Depends(get_memory_store),
) -> SearchResponse:
    """Hybrid search.

    Composite-score weights fall back to the configured global defaults
    (``weight_*`` in hebb.json) for any weight the request did not set
    explicitly — so callers like the recall hook honour the user's tuning,
    while the console Search sliders still override per query.

    Filter priority (highest to lowest):
    1. ``filter_score`` on the request (composite-score filtering, preferred)
    2. ``min_score`` on the request (legacy dual-scale filtering)
    3. ``filter_score`` from server config (when ``strict_recall=True``)
    4. No filtering (default for console search)

    Args:
        query: MemoryQuery with search parameters, weights, and filter settings.
        searcher: MemorySearcher instance for executing the search.
        settings: Server configuration with default weights and thresholds.
        store: MemoryStore for retrieval-induced strengthening.

    Returns:
        SearchResponse with ranked results and optional graph-expanded memories.

    Raises:
        ValueError: If query parameters are out of valid range.
    """
    updates: dict[str, object] = {
        field: getattr(settings, field)
        for field in ("weight_recency", "weight_importance", "weight_relevance")
        if field not in query.model_fields_set
    }
    # Strict recall surfaces (hook, MCP) opt in via ``strict_recall`` rather
    # than hardcoding a number — the floor lives in server config so the
    # console Settings edit is the single source of truth.
    #
    # Filter priority:
    # 1. filter_score on request → composite filtering (preferred)
    # 2. min_score on request → convert to filter_score (backward compat)
    # 3. Neither → inject settings.filter_score (default for strict_recall)
    if query.strict_recall and "filter_score" not in query.model_fields_set:
        if "min_score" in query.model_fields_set:
            # Backward compat: convert legacy min_score to filter_score
            updates["filter_score"] = query.min_score
        else:
            # Default: use configured filter_score
            updates["filter_score"] = settings.filter_score
    # Fill the rerank-scale translation ratio when the caller did not
    # explicitly pass it. This applies to both strict_recall and explicit
    # min_score paths so the searcher always has the correct scale.
    if "rerank_floor_ratio" not in query.model_fields_set:
        updates["rerank_floor_ratio"] = settings.rerank_floor_ratio
    if updates:
        query = query.model_copy(update=updates)
    response = await searcher.search(query)

    # Retrieval-induced strengthening: bump access for the memories we just
    # surfaced so the forgetting TTL / recency ranking treat them as alive
    # (the "use it or lose it" loop the search path otherwise never closed).
    # In-process recall during consolidation calls the searcher directly and
    # bypasses this. Gated on ``strict_recall`` so only genuine agent recall
    # (Claude Code hook / MCP, which opt in) strengthens — plain REST /search,
    # i.e. console browsing and ad-hoc queries, must NOT bias recency/forgetting
    # just by being looked at. Master switch off under benchmarks. (recall F8)
    if settings.recall_strengthening_enabled and query.strict_recall and response.results:
        await store.update_access_batch([r.memory.id for r in response.results])

    return response
