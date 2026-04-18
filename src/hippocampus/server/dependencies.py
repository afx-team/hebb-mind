"""FastAPI dependency injection."""

from __future__ import annotations

from fastapi import Request

from hippocampus.config.settings import Settings
from hippocampus.embedding.base import EmbeddingProvider
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.retrieval.searcher import MemorySearcher
from hippocampus.scheduler.manager import SchedulerManager
from hippocampus.storage.base import MemoryStore, PartitionStore


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_memory_store(request: Request) -> MemoryStore:
    return request.app.state.memory_store


def get_partition_store(request: Request) -> PartitionStore:
    return request.app.state.partition_store


def get_embedder(request: Request) -> EmbeddingProvider:
    return request.app.state.embedder


def get_knowledge_graph(request: Request) -> KnowledgeGraph:
    return request.app.state.knowledge_graph


def get_searcher(request: Request) -> MemorySearcher:
    return request.app.state.searcher


def get_scheduler(request: Request) -> SchedulerManager:
    return request.app.state.scheduler
