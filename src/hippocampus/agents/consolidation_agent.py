"""Consolidation Agent — processes working memory into long-term partitions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from hippocampus.agents.llm_client import LLMClient
from hippocampus.agents.prompts import (
    CONSOLIDATION_SYSTEM_PROMPT,
    CONSOLIDATION_USER_TEMPLATE,
    SESSION_CONSOLIDATION_SYSTEM_PROMPT,
    SESSION_CONSOLIDATION_USER_TEMPLATE,
)
from hippocampus.agents.recall_agent import RecallAgent
from hippocampus.config.settings import Settings
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

    # Overhead tokens for system prompt + related memories + output buffer
    _PROMPT_OVERHEAD_TOKENS = 2000

    def __init__(
        self,
        llm: LLMClient,
        recall_agent: RecallAgent,
        memory_store: MemoryStore,
        partition_store: PartitionStore,
        knowledge_graph: KnowledgeGraph,
        embedder: EmbeddingProvider,
        settings: Settings | None = None,
    ) -> None:
        self.llm = llm
        self.recall = recall_agent
        self.memory_store = memory_store
        self.partition_store = partition_store
        self.kg = knowledge_graph
        self.embedder = embedder
        max_tokens = settings.consolidation_max_tokens if settings else 16000
        # Convert token budget to char budget: ~4 chars/token, minus overhead
        self._max_chunk_chars = (max_tokens - self._PROMPT_OVERHEAD_TOKENS) * 4

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

    async def consolidate_session(self, memories: list[Memory]) -> list[ConsolidationResult]:
        """Consolidate a group of memories from the same session.

        Memories are sorted by turn, merged into a conversation context,
        and processed in a single LLM call that may produce multiple output memories.
        If the session is too long, it is split into chunks by turn order.
        """
        # Sort by turn (None last), then by created_at
        memories.sort(key=lambda m: (
            m.metadata.turn if m.metadata.turn is not None else 999999,
            m.created_at,
        ))

        # Split into chunks if too long
        chunks = self._split_into_chunks(memories)
        if len(chunks) > 1:
            session_id = memories[0].metadata.session_id or "unknown"
            logger.info(
                "Session %s too long (%d turns), split into %d chunks",
                session_id, len(memories), len(chunks),
            )

        all_results: list[ConsolidationResult] = []
        for chunk in chunks:
            rs = await self._consolidate_session_chunk(chunk)
            all_results.extend(rs)
        return all_results

    def _split_into_chunks(self, memories: list[Memory]) -> list[list[Memory]]:
        """Split memories into chunks that fit within the LLM context window."""
        chunks: list[list[Memory]] = []
        current: list[Memory] = []
        current_len = 0

        for m in memories:
            line_len = len(m.content) + 20  # overhead for "[Turn X] "
            if current and current_len + line_len > self._max_chunk_chars:
                chunks.append(current)
                current = []
                current_len = 0
            current.append(m)
            current_len += line_len

        if current:
            chunks.append(current)
        return chunks or [memories]

    async def _consolidate_session_chunk(self, memories: list[Memory]) -> list[ConsolidationResult]:
        """Consolidate one chunk of a session."""
        session_id = memories[0].metadata.session_id or "unknown"
        results: list[ConsolidationResult] = []

        try:
            # Build conversation turns text
            turns_text = "\n".join(
                f"[Turn {m.metadata.turn if m.metadata.turn is not None else '?'}] {m.content}"
                for m in memories
            )

            # Recall related memories using the conversation as context
            combined_content = " ".join(m.content for m in memories)
            related = await self.recall.recall(
                memory_content=combined_content[:2000],
                exclude_partition=PartitionType.HIPPOCAMPUS.value,
            )

            # Build partition and related descriptions
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

            # Single LLM call for the entire session
            messages = [
                {"role": "system", "content": SESSION_CONSOLIDATION_SYSTEM_PROMPT},
                {"role": "user", "content": SESSION_CONSOLIDATION_USER_TEMPLATE.format(
                    session_id=session_id,
                    turn_count=len(memories),
                    turns=turns_text,
                    partitions=partition_desc,
                    related_memories=related_desc,
                )},
            ]
            decision = await self.llm.complete_json(messages, temperature=0.3)

            output_memories = decision.get("memories", [])
            if not output_memories:
                # Fallback: treat as single memory
                output_memories = [decision] if "target_partition" in decision else []

            # Create each output memory
            for item in output_memories:
                target_partition = item.get("target_partition", PartitionType.SEMANTIC.value)
                content = item.get("consolidated_content", "")
                importance = item.get("importance_score", 5.0)
                tags = item.get("tags", [])
                conflicts = item.get("conflicts", [])

                if not content:
                    continue

                # Handle conflicts
                for conflict in conflicts:
                    conflict_id = conflict.get("memory_id", "")
                    resolution = conflict.get("resolution", "keep_both")
                    if resolution == "update" and conflict_id:
                        await self.memory_store.update(
                            conflict_id, MemoryUpdate(content=content),
                        )

                # Create consolidated memory
                embedding = await self.embedder.embed(content)
                new_memory = await self.memory_store.create(
                    data=MemoryCreate(
                        content=content,
                        partition_id=target_partition,
                        importance_score=importance,
                        tags=tags,
                        metadata={"session_id": session_id},
                        source="consolidation",
                    ),
                    embedding=embedding,
                )
                self.kg.update_from_tags(tags, new_memory.id)

                results.append(ConsolidationResult(
                    original_memory_id=f"session:{session_id}",
                    target_partition=target_partition,
                    new_memory_id=new_memory.id,
                    tags_extracted=tags,
                    success=True,
                ))

            # Delete all source memories from hippocampus
            for m in memories:
                await self.memory_store.delete(m.id)

            logger.info(
                "Session %s: %d turns → %d memories",
                session_id, len(memories), len(results),
            )

        except Exception as e:
            logger.error("Session consolidation failed for %s: %s", session_id, e, exc_info=True)
            results.append(ConsolidationResult(
                original_memory_id=f"session:{session_id}",
                success=False,
                error=str(e),
            ))

        return results

    async def consolidate_batch(self, concurrency: int = 5) -> list[ConsolidationResult]:
        """Process all memories in HIPPOCAMPUS partition.

        Groups memories by session_id (sorted by turn), consolidates each session
        in a single LLM call. Memories without session_id are processed individually.
        """
        memories = await self.memory_store.get_by_partition(
            PartitionType.HIPPOCAMPUS.value
        )

        # Group by session_id
        sessions: dict[str, list[Memory]] = {}
        standalone: list[Memory] = []
        for m in memories:
            sid = m.metadata.session_id if m.metadata.session_id else None
            if sid:
                sessions.setdefault(sid, []).append(m)
            elif m.metadata.turn is not None:
                # Has turn but no session_id — warn and treat as standalone
                logger.warning(
                    "Memory %s has turn=%d but no session_id, consolidating individually. "
                    "Set session_id for session-level consolidation.",
                    m.id, m.metadata.turn,
                )
                standalone.append(m)
            else:
                standalone.append(m)

        sem = asyncio.Semaphore(concurrency)
        kg_lock = asyncio.Lock()
        all_results: list[ConsolidationResult] = []
        lock = asyncio.Lock()

        # Process sessions
        async def _process_session(session_memories: list[Memory]) -> None:
            async with sem:
                rs = await self.consolidate_session(session_memories)
                async with kg_lock:
                    self.kg.save()
                async with lock:
                    all_results.extend(rs)

        # Process standalone memories
        async def _process_single(memory: Memory) -> None:
            async with sem:
                r = await self._consolidate_one(memory, kg_lock)
                async with lock:
                    all_results.append(r)

        tasks = [_process_session(mems) for mems in sessions.values()]
        tasks += [_process_single(m) for m in standalone]
        await asyncio.gather(*tasks)

        self.kg.save()

        session_count = len(sessions)
        standalone_count = len(standalone)
        succeeded = sum(1 for r in all_results if r.success)
        logger.info(
            "Consolidation complete: %d sessions + %d standalone → %d results (%d succeeded)",
            session_count, standalone_count, len(all_results), succeeded,
        )
        return all_results

    async def _consolidate_one(
        self, memory: "Memory", kg_lock: asyncio.Lock
    ) -> ConsolidationResult:
        """consolidate_memory variant that uses a lock for KG writes."""
        result = ConsolidationResult(original_memory_id=memory.id)
        try:
            related = await self.recall.recall(
                memory_content=memory.content,
                exclude_partition=PartitionType.HIPPOCAMPUS.value,
            )
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

            for conflict in conflicts:
                conflict_id = conflict.get("memory_id", "")
                resolution = conflict.get("resolution", "keep_both")
                if resolution == "update" and conflict_id:
                    await self.memory_store.update(
                        conflict_id, MemoryUpdate(content=consolidated_content),
                    )
                    result.conflicts_resolved += 1
                elif resolution == "discard":
                    await self.memory_store.delete(memory.id)
                    result.success = True
                    result.target_partition = "discarded"
                    return result

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

            async with kg_lock:
                self.kg.update_from_tags(tags, new_memory.id)

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
