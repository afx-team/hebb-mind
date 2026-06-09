"""Consolidation Agent — processes working memory into long-term partitions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from hebb.agents.llm_client import LLMClient
from hebb.agents.prompts import (
    CONSOLIDATION_SYSTEM_PROMPT,
    CONSOLIDATION_USER_TEMPLATE,
    SESSION_CONSOLIDATION_SYSTEM_PROMPT,
    SESSION_CONSOLIDATION_USER_TEMPLATE,
)
from hebb.agents.recall_agent import RecallAgent
from hebb.config.settings import Settings
from hebb.constants import PartitionType
from hebb.embedding.base import EmbeddingProvider
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import Memory, MemoryCreate, MemoryMetadata, MemoryUpdate
from hebb.storage.base import MemoryStore, PartitionStore
from hebb.storage.purge import purge_memory

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
        # Drain working memories the LLM judged low-value (well-formed empty
        # output) instead of keeping them forever — otherwise the inbox never
        # empties and the same small talk is re-sent to the LLM every run.
        # Defaults to True (also when settings is None, e.g. in tests).
        self._drain_empty = settings.consolidation_drain_empty_sources if settings else True
        # In-partition consolidation mode (set per consolidate_batch call).
        # ``_write_override``: force all consolidated writes into this
        # partition instead of the LLM-decided long-term partition.
        # ``_skip_recall``: skip cross-partition related-memory recall so a
        # scenario's summary never absorbs content from other partitions.
        # Both default off → production HIPPOCAMPUS→long-term flow unchanged.
        self._write_override: str | None = None
        self._skip_recall: bool = False

    async def _build_partition_desc(self) -> str:
        """Describe candidate long-term partitions for the LLM's target choice.

        Returns "" in in-partition mode (``_write_override`` set): the write
        target is forced to the source partition, so the list is unused — and
        enumerating ALL partitions (500+ in a per-scenario benchmark) would
        bloat every consolidation prompt and stall the LLM call.
        """
        if self._write_override is not None:
            return ""
        partitions = await self.partition_store.list()
        return "\n".join(
            f"- {p.id}: {p.name} — {p.description}"
            for p in partitions
            if p.id != PartitionType.HIPPOCAMPUS.value and p.enabled
        )

    async def consolidate_memory(self, memory: Memory) -> ConsolidationResult:
        """Process a single memory from HIPPOCAMPUS to a target partition."""
        result = ConsolidationResult(original_memory_id=memory.id)

        try:
            # Step 1: Recall related memories
            related: list[Memory] = []
            if not self._skip_recall:
                related = await self.recall.recall(
                    memory_content=memory.content,
                    exclude_partition=PartitionType.HIPPOCAMPUS.value,
                )
            recalled_ids = {m.id for m in related}

            # Step 2: Build context
            partition_desc = await self._build_partition_desc()

            related_desc = "None found."
            if related:
                related_desc = "\n".join(f"- [{m.id}] ({m.partition_id}): {m.content[:200]}" for m in related[:5])

            # Step 3: Ask LLM to consolidate
            messages = [
                {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": CONSOLIDATION_USER_TEMPLATE.format(
                        content=memory.content,
                        partitions=partition_desc,
                        related_memories=related_desc,
                    ),
                },
            ]
            decision = await self.llm.complete_json(messages, temperature=0.3)

            target_partition = self._write_override or decision.get("target_partition", PartitionType.SEMANTIC.value)
            consolidated_content = decision.get("consolidated_content", memory.content)
            importance = decision.get("importance_score", memory.importance_score)
            tags = decision.get("tags", memory.tags)
            conflicts = decision.get("conflicts", [])

            # Step 4: Handle conflicts (only against recalled ids; re-embed text).
            for conflict in conflicts:
                conflict_id = conflict.get("memory_id", "")
                resolution = conflict.get("resolution", "keep_both")
                if resolution == "update" and conflict_id in recalled_ids:
                    await self._apply_conflict_update(conflict_id, consolidated_content)
                    result.conflicts_resolved += 1
                elif resolution == "discard":
                    # New memory is redundant — delete it from every store.
                    await purge_memory(self.memory_store, self.kg, memory.id)
                    result.success = True
                    result.target_partition = "discarded"
                    return result

            # Empty-output guard: never write a placeholder + delete the source
            # on a garbled/empty LLM decision (silent data loss). Keep the
            # source for the next pass.
            if not consolidated_content or not consolidated_content.strip():
                logger.warning(
                    "Memory %s: consolidation produced empty content; keeping source "
                    "memory for the next pass (not deleting)",
                    memory.id,
                )
                result.success = True
                result.target_partition = "kept"
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

            # Step 6: Update knowledge graph with the new consolidated memory.
            self.kg.update_from_tags(tags, new_memory.id)

            # Step 7: Delete the source memory from every store (SQL + graph).
            # purge_memory strips the source id from the graph too — a no-op
            # unless the source was itself graphed (in-partition
            # re-consolidation) — and its kg.save() persists both the new tags
            # and the removal in one write.
            await purge_memory(self.memory_store, self.kg, memory.id)

            result.target_partition = target_partition
            result.new_memory_id = new_memory.id
            result.tags_extracted = tags
            result.success = True

        except Exception as e:
            logger.error("Consolidation failed for memory %s: %s", memory.id, e, exc_info=True)
            result.success = False
            result.error = str(e)

        return result

    async def consolidate_session(
        self, memories: list[Memory], kg_lock: asyncio.Lock | None = None
    ) -> list[ConsolidationResult]:
        """Consolidate a group of memories from the same session.

        Memories are sorted by turn, merged into a conversation context,
        and processed in a single LLM call that may produce multiple output memories.
        If the session is too long, it is split into chunks by turn order.

        Args:
            memories: Source memories belonging to one session.
            kg_lock: Optional lock serialising knowledge-graph mutations. When
                omitted, the graph's own shared lock (``self.kg.lock``) is used
                so concurrent sessions can never interleave a graph mutation
                with another task's save.

        Returns:
            One ``ConsolidationResult`` per produced (or failed) memory.
        """
        # Sort by turn (None last), then by created_at
        memories.sort(
            key=lambda m: (
                m.metadata.turn if m.metadata.turn is not None else 999999,
                m.created_at,
            )
        )

        # Split into chunks if too long
        chunks = self._split_into_chunks(memories)
        if len(chunks) > 1:
            session_id = memories[0].metadata.session_id or "unknown"
            logger.info(
                "Session %s too long (%d turns), split into %d chunks",
                session_id,
                len(memories),
                len(chunks),
            )

        lock = kg_lock or self.kg.lock
        all_results: list[ConsolidationResult] = []
        for chunk in chunks:
            rs = await self._consolidate_session_chunk(chunk, lock)
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

    async def _consolidate_session_chunk(
        self, memories: list[Memory], kg_lock: asyncio.Lock
    ) -> list[ConsolidationResult]:
        """Consolidate one chunk of a session.

        Args:
            memories: Source memories for this chunk (already turn-sorted).
            kg_lock: Lock serialising all knowledge-graph mutations + saves.

        Returns:
            One ``ConsolidationResult`` per produced (or failed) memory.
        """
        session_id = memories[0].metadata.session_id or "unknown"
        results: list[ConsolidationResult] = []

        # Carry temporal/turn anchors from the source turns onto the
        # consolidated output. Without this the session path emitted bare
        # ``MemoryMetadata(session_id=...)`` and dropped every other field:
        #   * turn_pair — the [min, max] turn span lets turn-window expansion
        #     anchor the consolidated memory back to its conversation position.
        #   * timestamp — the earliest source timestamp is what the searcher's
        #     temporal_boost reads (metadata.timestamp); dropping it made date
        #     queries blind to consolidated memories.
        turn_anchors = [m.metadata.turn for m in memories if m.metadata.turn is not None]
        source_ts = [str(ts) for m in memories if (ts := m.metadata.model_dump().get("timestamp"))]
        session_meta: dict[str, object] = {"session_id": session_id}
        if turn_anchors:
            session_meta["turn_pair"] = [min(turn_anchors), max(turn_anchors)]
        if source_ts:
            session_meta["timestamp"] = min(source_ts)

        try:
            # Build conversation turns text
            turns_text = "\n".join(
                f"[Turn {m.metadata.turn if m.metadata.turn is not None else '?'}] {m.content}" for m in memories
            )

            # Recall related memories using the conversation as context.
            # Skipped in in-partition mode so a scenario's summary never
            # absorbs content recalled from other partitions.
            related: list[Memory] = []
            if not self._skip_recall:
                combined_content = " ".join(m.content for m in memories)
                related = await self.recall.recall(
                    memory_content=combined_content[:2000],
                    exclude_partition=PartitionType.HIPPOCAMPUS.value,
                )

            # Build partition descriptions for the LLM's target choice.
            # Skipped in in-partition mode: the target is overridden to the
            # source partition, so the partition list is irrelevant — and
            # listing ALL partitions (500+ in a per-scenario benchmark)
            # would bloat every prompt and stall the LLM call.
            partition_desc = await self._build_partition_desc()
            related_desc = "None found."
            if related:
                related_desc = "\n".join(f"- [{m.id}] ({m.partition_id}): {m.content[:200]}" for m in related[:5])

            # Only ids we actually recalled are valid conflict targets. The LLM
            # can hallucinate ids; updating an unrelated id silently corrupts a
            # memory we never showed it.
            recalled_ids = {m.id for m in related}

            # Single LLM call for the entire session
            messages = [
                {"role": "system", "content": SESSION_CONSOLIDATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": SESSION_CONSOLIDATION_USER_TEMPLATE.format(
                        session_id=session_id,
                        turn_count=len(memories),
                        turns=turns_text,
                        partitions=partition_desc,
                        related_memories=related_desc,
                    ),
                },
            ]
            decision = await self.llm.complete_json(messages, temperature=0.3)

            output_memories = decision.get("memories", [])
            if not output_memories:
                # Fallback: treat as single memory
                output_memories = [decision] if "target_partition" in decision else []

            # Create each output memory
            for item in output_memories:
                target_partition = self._write_override or item.get("target_partition", PartitionType.SEMANTIC.value)
                content = item.get("consolidated_content", "")
                importance = item.get("importance_score", 5.0)
                tags = item.get("tags", [])
                conflicts = item.get("conflicts", [])

                if not content:
                    continue

                # Handle conflicts (only against ids we actually recalled; the
                # updated text is re-embedded so the vector matches it).
                for conflict in conflicts:
                    conflict_id = conflict.get("memory_id", "")
                    resolution = conflict.get("resolution", "keep_both")
                    if resolution == "update" and conflict_id in recalled_ids:
                        await self._apply_conflict_update(conflict_id, content)

                # Create consolidated memory
                embedding = await self.embedder.embed(content)
                new_memory = await self.memory_store.create(
                    data=MemoryCreate(
                        content=content,
                        partition_id=target_partition,
                        importance_score=importance,
                        tags=tags,
                        metadata=MemoryMetadata.model_validate(session_meta),
                        source="consolidation",
                    ),
                    embedding=embedding,
                )
                async with kg_lock:
                    self.kg.update_from_tags(tags, new_memory.id)

                results.append(
                    ConsolidationResult(
                        original_memory_id=f"session:{session_id}",
                        target_partition=target_partition,
                        new_memory_id=new_memory.id,
                        tags_extracted=tags,
                        success=True,
                    )
                )

            # Delete the source memories — but ONLY if we actually produced
            # consolidated output. A successful-but-empty LLM response (no
            # "memories", or every item skipped for empty content) must NOT wipe
            # the sources: that is silent data loss with zero replacement. Keep
            # them in the working partition for the next consolidation pass.
            if results:
                async with kg_lock:
                    for m in memories:
                        await self.memory_store.delete(m.id)
                        # Strip the source id from the graph (no-op unless the
                        # source was itself graphed, i.e. in-partition
                        # re-consolidation).
                        self.kg.remove_memory_from_tags(m.id)
                    # Persist the graph immediately after the SQL deletes, under
                    # the same lock, to shrink the crash window between "source
                    # row deleted" and "graph reference removed". The caller's
                    # end-of-batch save() is now a redundant safety net rather
                    # than the only persistence point.
                    self.kg.save()
            elif self._drain_empty and "memories" in decision and not decision.get("memories"):
                # Well-formed empty result: the model read the whole conversation
                # and deliberately returned an empty "memories" list — i.e. it
                # judged the turns low-value (small talk, greetings; see the
                # prompt's "discard ... no long-term value" guideline). Drain
                # these sources so the inbox empties instead of re-sending the
                # same content to the LLM on every run forever.
                #
                # Safety: a garbled/unparseable response makes complete_json
                # return {} (no "memories" key), so it falls through to the keep
                # branch below — a transient/parse failure never deletes data.
                preview = " | ".join(m.content[:60].replace("\n", " ") for m in memories[:3])
                logger.info(
                    "Session %s: LLM found nothing worth keeping; draining %d low-value source memories [%s]",
                    session_id,
                    len(memories),
                    preview,
                )
                async with kg_lock:
                    for m in memories:
                        await self.memory_store.delete(m.id)
                        self.kg.remove_memory_from_tags(m.id)
                    self.kg.save()
                # Report the drained sources so the run summary counts them as
                # processed (progress) rather than reporting "0 ok" every pass.
                results = [
                    ConsolidationResult(
                        original_memory_id=f"session:{session_id}",
                        target_partition="discarded",
                        success=True,
                    )
                    for _ in memories
                ]
            else:
                logger.warning(
                    "Session %s: consolidation produced no output memories; "
                    "keeping %d source memories for the next pass (not deleting)",
                    session_id,
                    len(memories),
                )

            logger.info(
                "Session %s: %d turns → %d memories",
                session_id,
                len(memories),
                len(results),
            )

        except Exception as e:
            logger.error("Session consolidation failed for %s: %s", session_id, e, exc_info=True)
            results.append(
                ConsolidationResult(
                    original_memory_id=f"session:{session_id}",
                    success=False,
                    error=str(e),
                )
            )

        return results

    async def _apply_conflict_update(self, conflict_id: str, content: str) -> None:
        """Apply a conflict ``update`` resolution to an existing memory.

        Updates the memory's content AND re-embeds it so the stored vec0 vector
        matches the new text — otherwise vector recall keeps scoring the stale
        embedding against the updated content.

        Args:
            conflict_id: Id of the recalled memory being updated. Must be an id
                we actually recalled (the caller is responsible for that check).
            content: The new consolidated content to write.

        Returns:
            None.
        """
        if not content.strip():
            # Never overwrite a real memory with empty/whitespace content.
            return
        updated = await self.memory_store.update(conflict_id, MemoryUpdate(content=content))
        if updated is None:
            return
        # Re-embed so the vector matches the updated text.
        embedding = await self.embedder.embed(content)
        await self.memory_store.update_embedding(conflict_id, embedding)

    async def consolidate_batch(
        self,
        concurrency: int = 5,
        source_partition: str | None = None,
        keep_partition: bool = False,
    ) -> list[ConsolidationResult]:
        """Process all memories in a partition (default HIPPOCAMPUS).

        Groups memories by session_id (sorted by turn), consolidates each session
        in a single LLM call. Memories without session_id are processed individually.

        Args:
            concurrency: Max concurrent session/standalone consolidations.
            source_partition: Partition to read working memories from. Defaults
                to HIPPOCAMPUS (the production working-memory partition).
            keep_partition: When True, consolidated memories are written back
                into ``source_partition`` (overriding the LLM's target) and
                cross-partition recall is skipped. Required for per-scenario
                benches (LongMemEval/ConvoMem) whose retrieval is
                partition-scoped — without it, consolidated memories land in a
                global long-term partition and become invisible at eval time.
        """
        read_partition = source_partition or PartitionType.HIPPOCAMPUS.value
        self._write_override = read_partition if keep_partition else None
        self._skip_recall = keep_partition
        memories = await self.memory_store.get_by_partition(read_partition)

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
                    m.id,
                    m.metadata.turn,
                )
                standalone.append(m)
            else:
                standalone.append(m)

        sem = asyncio.Semaphore(concurrency)
        # Use the graph's own shared lock so every read-modify-write + save
        # across the consolidation and forgetting paths serialises through one
        # consistent lock (previously a per-batch lock left the session path's
        # graph mutations unsynchronised — race F4 / C1).
        kg_lock = self.kg.lock
        all_results: list[ConsolidationResult] = []
        lock = asyncio.Lock()

        # Process sessions. The session path persists the graph itself (under
        # kg_lock) after its SQL deletes, so no extra save() is needed here.
        async def _process_session(session_memories: list[Memory]) -> None:
            async with sem:
                rs = await self.consolidate_session(session_memories, kg_lock)
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

        async with kg_lock:
            self.kg.save()

        session_count = len(sessions)
        standalone_count = len(standalone)
        succeeded = sum(1 for r in all_results if r.success)
        logger.info(
            "Consolidation complete: %d sessions + %d standalone → %d results (%d succeeded)",
            session_count,
            standalone_count,
            len(all_results),
            succeeded,
        )
        return all_results

    async def _consolidate_one(self, memory: Memory, kg_lock: asyncio.Lock) -> ConsolidationResult:
        """Consolidate a single standalone memory using a shared KG lock.

        ``consolidate_memory`` variant that serialises knowledge-graph writes
        through ``kg_lock`` for concurrent batch processing.

        Args:
            memory: The source memory to consolidate.
            kg_lock: Lock serialising all knowledge-graph mutations + saves.

        Returns:
            The ``ConsolidationResult`` for this memory.
        """
        result = ConsolidationResult(original_memory_id=memory.id)
        try:
            related: list[Memory] = []
            if not self._skip_recall:
                related = await self.recall.recall(
                    memory_content=memory.content,
                    exclude_partition=PartitionType.HIPPOCAMPUS.value,
                )
            recalled_ids = {m.id for m in related}
            partition_desc = await self._build_partition_desc()
            related_desc = "None found."
            if related:
                related_desc = "\n".join(f"- [{m.id}] ({m.partition_id}): {m.content[:200]}" for m in related[:5])
            messages = [
                {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": CONSOLIDATION_USER_TEMPLATE.format(
                        content=memory.content,
                        partitions=partition_desc,
                        related_memories=related_desc,
                    ),
                },
            ]
            decision = await self.llm.complete_json(messages, temperature=0.3)

            target_partition = self._write_override or decision.get("target_partition", PartitionType.SEMANTIC.value)
            consolidated_content = decision.get("consolidated_content", memory.content)
            importance = decision.get("importance_score", memory.importance_score)
            tags = decision.get("tags", memory.tags)
            conflicts = decision.get("conflicts", [])

            # Handle conflicts first so an explicit ``discard`` still works even
            # when no consolidated content is produced.
            for conflict in conflicts:
                conflict_id = conflict.get("memory_id", "")
                resolution = conflict.get("resolution", "keep_both")
                if resolution == "update" and conflict_id in recalled_ids:
                    # Only update ids we actually recalled; re-embed the new text.
                    await self._apply_conflict_update(conflict_id, consolidated_content)
                    result.conflicts_resolved += 1
                elif resolution == "discard":
                    async with kg_lock:
                        self.kg.remove_memory_from_tags(memory.id)
                        self.kg.save()
                    await self.memory_store.delete(memory.id)
                    result.success = True
                    result.target_partition = "discarded"
                    return result

            # Empty-output guard: a garbled/empty LLM decision must NOT write a
            # placeholder memory and then delete the source — that is silent
            # data loss with no replacement. Keep the source intact for the next
            # pass. (Mirrors the session path's empty-output guard at line ~381.)
            if not consolidated_content or not consolidated_content.strip():
                logger.warning(
                    "Memory %s: consolidation produced empty content; keeping source "
                    "memory for the next pass (not deleting)",
                    memory.id,
                )
                result.success = True
                result.target_partition = "kept"
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
                # Strip the source id under the same lock (no-op unless the
                # source was graphed via in-partition re-consolidation).
                self.kg.remove_memory_from_tags(memory.id)
                await self.memory_store.delete(memory.id)
                # Persist the graph immediately after the SQL delete, under the
                # same lock, to shrink the crash window. The end-of-batch save()
                # is now a redundant safety net.
                self.kg.save()

            result.target_partition = target_partition
            result.new_memory_id = new_memory.id
            result.tags_extracted = tags
            result.success = True
        except Exception as e:
            logger.error("Consolidation failed for memory %s: %s", memory.id, e, exc_info=True)
            result.success = False
            result.error = str(e)
        return result
