"""Knowledge graph data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TagNode(BaseModel):
    """A tag node in the knowledge graph."""

    id: str
    label: str = ""
    description: str = ""
    memory_ids: list[str] = Field(default_factory=list)
    weight: float = 1.0


class TagEdge(BaseModel):
    """An edge between two tags in the knowledge graph."""

    source: str
    target: str
    relation: str = "related"
    weight: float = 1.0


class KnowledgeGraphState(BaseModel):
    """Serializable state of the knowledge graph."""

    nodes: list[TagNode] = Field(default_factory=list)
    edges: list[TagEdge] = Field(default_factory=list)
    version: int = 1


class GraphQueryResult(BaseModel):
    """Result of a graph query."""

    nodes: list[TagNode] = Field(default_factory=list)
    edges: list[TagEdge] = Field(default_factory=list)
    paths: list[list[str]] | None = None
