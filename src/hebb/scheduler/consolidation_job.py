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
    source_partitions: list[str] | None = None,
    keep_partition: bool = False,
) -> list[ConsolidationResult]:
    """Run consolidation for all pending memories.

    Args:
        source_partitions: When given, consolidate each of these partitions
            in turn instead of the global HIPPOCAMPUS working partition. Used
            by per-scenario benchmarks (LongMemEval/ConvoMem) to consolidate
            each isolated scenario partition.
        keep_partition: Forwarded to ``consolidate_batch`` — write consolidated
            memories back into the source partition (preserving per-scenario
            isolation) instead of moving them to a long-term partition.
    """
    # Guard the scheduled/library path the same way the API ``consolidate()``
    # handler does: with no ``llm_model`` configured, building an LLMClient and
    # calling litellm with ``model=None`` raises on every daily run. Skip
    # cleanly instead (LLM config F3).
    if not settings.llm_model:
        logger.info("Skipping consolidation: no llm_model configured")
        return []

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

    if source_partitions:
        all_results: list[ConsolidationResult] = []
        for idx, partition_id in enumerate(source_partitions, 1):
            rs = await agent.consolidate_batch(
                concurrency=settings.consolidation_concurrency,
                source_partition=partition_id,
                keep_partition=keep_partition,
            )
            all_results.extend(rs)
            if idx % 25 == 0 or idx == len(source_partitions):
                logger.info(
                    "Per-partition consolidation progress: %d/%d partitions",
                    idx,
                    len(source_partitions),
                )
    else:
        all_results = await agent.consolidate_batch(concurrency=settings.consolidation_concurrency)

    succeeded = sum(1 for r in all_results if r.success)
    logger.info("Consolidation complete: %d/%d succeeded", succeeded, len(all_results))
    return all_results
