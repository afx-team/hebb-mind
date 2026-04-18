"""Consolidation Agent — processes working memory into long-term partitions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from hippocampus.agents.llm_client import LLMClient
from hippocampus.agents.prompts import (
    CONSOLIDATION_SYSTEM_PROMPT,
    CONSOLIDATION_USER_TEMPLATE,
)
from hippocampus.agents.recall_agent import RecallAgent
from hippocampus.constants import PartitionType
from hippocampus.embedding.base import EmbeddingProvider
from hippocampus.graph.knowledge_graph import KnowledgeGraph
from hippocampus.models.memory import Memory, MemoryCreate, MemoryUpdate
from hippocampus.storage.base import MemoryStore, PartitionStore

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationResult:
    original_memory_id: str
    target_partition: str = ""
    new_memory_id: str = ""
    tags_extracted: list[str] = field(default_factory=list)
    conflicts_resolved: int = 0
    success: bool = True
    error: str | None = None


class ConsolidationAgent:
    """Processes memories from HIPPOCAMPUS partition into appropriate long-term partitions."""

    def __init__(
        self,
        llm: LLMClient,
        recall_agent: RecallAgent,
        memory_store: MemoryStore,
        partition_store: PartitionStore,
        knowledge_graph: KnowledgeGraph,
        embedder: EmbeddingProvider,
    ) -> None:
        self.llm = llm
        self.recall = recall_agent
        self.memory_store = memory_store
        self.partition_store = partition_store
        self.kg = knowledge_graph
        self.embedder = embedder

    async def consolidate_memory(self, memory: Memory) -> ConsolidationResult:
        """Process a single memory from HIPPOCAMPUS to a target partition."""
        result = ConsolidationResult(original_memory_id=memory.id)

        try:
            # Step 1: Recall related memories
            related = await self.recall.recall(
                memory_content=memory.content,
                exclude_partition=PartitionType.HIPPOCAMPUS.value,
            )

            # Step 2: Build context
            partitions = await self.partition_store.list()
            partition_desc = "\n".join(
                f"- {p.id}: {p.name} — {p.description}"
                for p in partitions
                if p.id != PartitionType.HIPPOCAMPUS.value and p.enabled
            )

            related_desc = "None found."
            if related:
                related_desc = "\n".join(
                    f"- [{m.id}] ({m.partition_id}): {m.content[:200]}"
                    for m in related[:5]
                )

            # Step 3: Ask LLM to consolidate
            messages = [
                {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
                {"role": "user", "content": CONSOLIDATION_USER_TEMPLATE.format(
                    content=memory.content,
                    partitions=partition_desc,
                    related_memories=related_desc,
                )},
            ]
            decision = await self.llm.complete_json(messages, temperature=0.3)

            target_partition = decision.get("target_partition", PartitionType.SEMANTIC.value)
            consolidated_content = decision.get("consolidated_content", memory.content)
            importance = decision.get("importance_score", memory.importance_score)
            tags = decision.get("tags", memory.tags)
            conflicts = decision.get("conflicts", [])

            # Step 4: Handle conflicts
            for conflict in conflicts:
                conflict_id = conflict.get("memory_id", "")
                resolution = conflict.get("resolution", "keep_both")
                if resolution == "update" and conflict_id:
                    await self.memory_store.update(
                        conflict_id,
                        MemoryUpdate(content=consolidated_content),
                    )
                    result.conflicts_resolved += 1
                elif resolution == "discard":
                    # New memory is redundant, just delete from hippocampus
                    await self.memory_store.delete(memory.id)
                    result.success = True
                    result.target_partition = "discarded"
                    return result

            # Step 5: Write consolidated memory to target partition
            embedding = await self.embedder.embed(consolidated_content)
            new_memory = await self.memory_store.create(
                data=MemoryCreate(
                    content=consolidated_content,
                    partition_id=target_partition,
                    importance_score=importance,
                    tags=tags,
                    metadata=memory.metadata,
                    source="consolidation",
                ),
                embedding=embedding,
            )

            # Step 6: Update knowledge graph
            self.kg.update_from_tags(tags, new_memory.id)
            self.kg.save()

            # Step 7: Delete from hippocampus
            await self.memory_store.delete(memory.id)

            result.target_partition = target_partition
            result.new_memory_id = new_memory.id
            result.tags_extracted = tags
            result.success = True

        except Exception as e:
            logger.error("Consolidation failed for memory %s: %s", memory.id, e, exc_info=True)
            result.success = False
            result.error = str(e)

        return result

    async def consolidate_batch(self) -> list[ConsolidationResult]:
        """Process all memories in HIPPOCAMPUS partition."""
        memories = await self.memory_store.get_by_partition(
            PartitionType.HIPPOCAMPUS.value
        )
        results = []
        for memory in memories:
            r = await self.consolidate_memory(memory)
            results.append(r)
            logger.info(
                "Consolidated memory %s -> %s (success=%s)",
                r.original_memory_id, r.target_partition, r.success,
            )
        return results
