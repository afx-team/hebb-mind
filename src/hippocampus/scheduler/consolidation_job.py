"""Consolidation job — periodic batch processing of HIPPOCAMPUS memories."""

from __future__ import annotations

import logging

from hippocampus.agents.consolidation_agent import ConsolidationAgent, ConsolidationResult
from hippocampus.agents.llm_client import LLMClient
from hippocampus.agents.recall_agent import RecallAgent
from hippocampus.config.settings import Settings
from hippocampus.embedding.base import EmbeddingProvider
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.retrieval.searcher import MemorySearcher
from hippocampus.storage.base import MemoryStore, PartitionStore

logger = logging.getLogger(__name__)


async def run_consolidation(
    memory_store: MemoryStore,
    partition_store: PartitionStore,
    knowledge_graph: KnowledgeGraph,
    embedder: EmbeddingProvider,
    settings: Settings,
) -> list[ConsolidationResult]:
    """Run consolidation for all pending memories."""
    llm = LLMClient(settings)
    searcher = MemorySearcher(store=memory_store, embedder=embedder)
    recall_agent = RecallAgent(llm=llm, searcher=searcher)
    agent = ConsolidationAgent(
        llm=llm,
        recall_agent=recall_agent,
        memory_store=memory_store,
        partition_store=partition_store,
        knowledge_graph=knowledge_graph,
        embedder=embedder,
    )

    all_results = await agent.consolidate_batch()

    succeeded = sum(1 for r in all_results if r.success)
    logger.info("Consolidation complete: %d/%d succeeded", succeeded, len(all_results))
    return all_results
