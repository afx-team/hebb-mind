"""Tests for ConsolidationAgent (mocked LLM via the shared ``mock_llm`` fixture)."""

from __future__ import annotations

import pytest

from hebb.agents.consolidation_agent import ConsolidationAgent
from hebb.agents.recall_agent import RecallAgent
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import MemoryCreate, MemoryMetadata
from hebb.retrieval.searcher import MemorySearcher


class TestConsolidationAgent:
    @pytest.mark.asyncio
    async def test_consolidate_memory(self, mock_llm, memory_store, partition_store, noop_embedder, tmp_path):
        """Consolidation should move memory from hebb to target partition."""
        kg = KnowledgeGraph(tmp_path / "kg.json")

        # Create a memory in hebb
        mem = await memory_store.create(
            MemoryCreate(content="User prefers dark mode", partition_id="mem_hippocampus"),
        )

        # Mock LLM: recall returns no queries, consolidation returns classification
        mock_llm.complete_json.side_effect = [
            # RecallAgent.recall -> generate queries
            {"queries": ["user preference"]},
            # ConsolidationAgent -> classify memory
            {
                "target_partition": "mem_preference",
                "consolidated_content": "User prefers dark mode for UI.",
                "importance_score": 7.0,
                "tags": ["preference", "ui", "dark-mode"],
                "conflicts": [],
                "reasoning": "This is a user preference about UI appearance.",
            },
        ]

        recall_agent = RecallAgent(
            llm=mock_llm,
            searcher=MemorySearcher(store=memory_store, embedder=noop_embedder),
        )
        agent = ConsolidationAgent(
            llm=mock_llm,
            recall_agent=recall_agent,
            memory_store=memory_store,
            partition_store=partition_store,
            knowledge_graph=kg,
            embedder=noop_embedder,
        )

        result = await agent.consolidate_memory(mem)

        assert result.success
        assert result.target_partition == "mem_preference"
        assert "preference" in result.tags_extracted

        # Original memory should be deleted from hebb
        original = await memory_store.get(mem.id)
        assert original is None

        # New memory should exist in preference partition
        prefs = await memory_store.get_by_partition("mem_preference")
        assert len(prefs) == 1
        assert "dark mode" in prefs[0].content

        # KG should have tags
        assert kg.get_tag("preference") is not None
        assert kg.get_tag("ui") is not None

    @pytest.mark.asyncio
    async def test_session_consolidation_preserves_turn_and_timestamp(
        self, mock_llm, memory_store, partition_store, noop_embedder, tmp_path
    ):
        """Session consolidation must carry the source turns' turn span and
        earliest timestamp onto the consolidated memory (so turn-window
        expansion and temporal_boost still work on consolidated output)."""
        kg = KnowledgeGraph(tmp_path / "kg.json")

        m1 = await memory_store.create(
            MemoryCreate(
                content="User mentions they live in Sweden",
                partition_id="mem_hippocampus",
                metadata=MemoryMetadata.model_validate(
                    {"session_id": "s1", "turn": 0, "timestamp": "2023-08-01T10:00:00+00:00"}
                ),
            )
        )
        m2 = await memory_store.create(
            MemoryCreate(
                content="User says they read a book by Tom Oliver",
                partition_id="mem_hippocampus",
                metadata=MemoryMetadata.model_validate(
                    {"session_id": "s1", "turn": 1, "timestamp": "2023-08-01T10:05:00+00:00"}
                ),
            )
        )

        mock_llm.complete_json.side_effect = [
            {"queries": ["sweden book"]},  # RecallAgent
            {
                "memories": [
                    {
                        "target_partition": "mem_episodic",
                        "consolidated_content": "User lives in Sweden and read a book by Tom Oliver.",
                        "importance_score": 6.0,
                        "tags": ["sweden", "book"],
                        "conflicts": [],
                    }
                ]
            },
        ]

        recall_agent = RecallAgent(
            llm=mock_llm,
            searcher=MemorySearcher(store=memory_store, embedder=noop_embedder),
        )
        agent = ConsolidationAgent(
            llm=mock_llm,
            recall_agent=recall_agent,
            memory_store=memory_store,
            partition_store=partition_store,
            knowledge_graph=kg,
            embedder=noop_embedder,
        )

        results = await agent.consolidate_session([m1, m2])
        assert len(results) == 1 and results[0].success

        episodic = await memory_store.get_by_partition("mem_episodic")
        assert len(episodic) == 1
        meta = episodic[0].metadata.model_dump()
        assert meta["session_id"] == "s1"
        assert meta["turn_pair"] == [0, 1]
        assert meta["timestamp"] == "2023-08-01T10:00:00+00:00"

    @pytest.mark.asyncio
    async def test_consolidate_batch_empty(self, mock_llm, memory_store, partition_store, noop_embedder, tmp_path):
        """Batch consolidation with no hebb memories returns empty list."""
        kg = KnowledgeGraph(tmp_path / "kg.json")

        recall_agent = RecallAgent(
            llm=mock_llm,
            searcher=MemorySearcher(store=memory_store, embedder=noop_embedder),
        )
        agent = ConsolidationAgent(
            llm=mock_llm,
            recall_agent=recall_agent,
            memory_store=memory_store,
            partition_store=partition_store,
            knowledge_graph=kg,
            embedder=noop_embedder,
        )

        results = await agent.consolidate_batch()
        assert results == []

    @pytest.mark.asyncio
    async def test_consolidate_handles_conflict_discard(
        self, mock_llm, memory_store, partition_store, noop_embedder, tmp_path
    ):
        """When LLM says discard, the memory is deleted without creating a new one."""
        kg = KnowledgeGraph(tmp_path / "kg.json")

        mem = await memory_store.create(
            MemoryCreate(content="redundant info", partition_id="mem_hippocampus"),
        )

        mock_llm.complete_json.side_effect = [
            {"queries": []},
            {
                "target_partition": "mem_semantic",
                "consolidated_content": "redundant",
                "importance_score": 3.0,
                "tags": ["test"],
                "conflicts": [{"memory_id": "some-old-id", "resolution": "discard", "reason": "duplicate"}],
            },
        ]

        recall_agent = RecallAgent(
            llm=mock_llm,
            searcher=MemorySearcher(store=memory_store, embedder=noop_embedder),
        )
        agent = ConsolidationAgent(
            llm=mock_llm,
            recall_agent=recall_agent,
            memory_store=memory_store,
            partition_store=partition_store,
            knowledge_graph=kg,
            embedder=noop_embedder,
        )

        result = await agent.consolidate_memory(mem)
        assert result.success
        assert result.target_partition == "discarded"

        # Original should be gone
        assert await memory_store.get(mem.id) is None
