"""FastAPI dependency injection."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from hebb.config.settings import Settings
from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.retrieval.searcher import MemorySearcher
from hebb.scheduler.manager import SchedulerManager
from hebb.storage.base import MemoryStore, PartitionStore


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_memory_store(request: Request) -> MemoryStore:
    return cast(MemoryStore, request.app.state.memory_store)


def get_partition_store(request: Request) -> PartitionStore:
    return cast(PartitionStore, request.app.state.partition_store)


def get_embedder(request: Request) -> EmbeddingProvider:
    return cast(EmbeddingProvider, request.app.state.embedder)


def get_knowledge_graph(request: Request) -> KnowledgeGraph:
    return cast(KnowledgeGraph, request.app.state.knowledge_graph)


def get_searcher(request: Request) -> MemorySearcher:
    return cast(MemorySearcher, request.app.state.searcher)


def get_scheduler(request: Request) -> SchedulerManager:
    return cast(SchedulerManager, request.app.state.scheduler)
