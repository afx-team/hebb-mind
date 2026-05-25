"""Memory search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hebb.models.memory import MemoryQuery, SearchResponse
from hebb.retrieval.searcher import MemorySearcher
from hebb.server.dependencies import get_searcher

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_memories(
    query: MemoryQuery,
    searcher: MemorySearcher = Depends(get_searcher),
) -> SearchResponse:
    return await searcher.search(query)
