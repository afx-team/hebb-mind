"""Consolidation job — periodic batch processing of HIPPOCAMPUS memories."""

from __future__ import annotations

import logging

from hebb.agents.consolidation_agent import ConsolidationAgent, ConsolidationResult
from hebb.agents.llm_client import LLMClient
from hebb.agents.recall_agent import RecallAgent
from hebb.config.settings import Settings
from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.retrieval.searcher import MemorySearcher
from hebb.storage.base import MemoryStore, PartitionStore

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
        settings=settings,
    )

    all_results = await agent.consolidate_batch(concurrency=settings.consolidation_concurrency)

    succeeded = sum(1 for r in all_results if r.success)
    logger.info("Consolidation complete: %d/%d succeeded", succeeded, len(all_results))
    return all_results
