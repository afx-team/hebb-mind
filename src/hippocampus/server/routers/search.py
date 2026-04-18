"""Memory search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hippocampus.models.memory import MemoryQuery, SearchResponse
from hippocampus.retrieval.searcher import MemorySearcher
from hippocampus.server.dependencies import get_searcher

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_memories(
    query: MemoryQuery,
    searcher: MemorySearcher = Depends(get_searcher),
):
    return await searcher.search(query)
