"""Knowledge graph endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.models.graph import GraphQueryResult, KnowledgeGraphState, TagNode
from hippocampus.server.dependencies import get_knowledge_graph

router = APIRouter()


@router.get("/graph/tags", response_model=list[TagNode])
async def list_tags(
    q: str | None = Query(default=None),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
):
    if q:
        return kg.search_tags(q)
    return kg.get_all_tags()


@router.get("/graph/tags/{tag_id}", response_model=TagNode)
async def get_tag(
    tag_id: str,
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
):
    tag = kg.get_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.get("/graph/neighbors/{tag_id}", response_model=GraphQueryResult)
async def get_neighbors(
    tag_id: str,
    depth: int = Query(default=1, ge=1, le=5),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
):
    return kg.query_neighbors(tag_id, depth)


@router.get("/graph/path", response_model=GraphQueryResult)
async def find_path(
    source: str = Query(..., alias="from"),
    target: str = Query(..., alias="to"),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
):
    return kg.search_path(source, target)


@router.get("/graph/export", response_model=KnowledgeGraphState)
async def export_graph(
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
):
    return kg.export()
