"""Memory search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hebb.config.settings import Settings
from hebb.models.memory import MemoryQuery, SearchResponse
from hebb.retrieval.searcher import MemorySearcher
from hebb.server.dependencies import get_searcher, get_settings

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_memories(
    query: MemoryQuery,
    searcher: MemorySearcher = Depends(get_searcher),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    """Hybrid search.

    Composite-score weights fall back to the configured global defaults
    (``weight_*`` in hebb.json) for any weight the request did not set
    explicitly — so callers like the recall hook honour the user's tuning,
    while the console Search sliders still override per query.
    """
    weight_updates = {
        field: getattr(settings, field)
        for field in ("weight_recency", "weight_importance", "weight_relevance")
        if field not in query.model_fields_set
    }
    if weight_updates:
        query = query.model_copy(update=weight_updates)
    return await searcher.search(query)
