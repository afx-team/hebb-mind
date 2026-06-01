"""Tests for RecallAgent (mocked LLM via the shared ``mock_llm`` fixture)."""

from __future__ import annotations

import pytest

from hebb.agents.recall_agent import RecallAgent
from hebb.models.memory import MemoryCreate
from hebb.retrieval.searcher import MemorySearcher


class TestRecallAgent:
    @pytest.mark.asyncio
    async def test_recall_generates_queries_and_searches(self, mock_llm, memory_store, noop_embedder):
        """RecallAgent should ask LLM for queries, then search with each."""
        mock_llm.complete_json.return_value = {"queries": ["dark mode preference", "UI settings"]}
        searcher = MemorySearcher(store=memory_store, embedder=noop_embedder)
        agent = RecallAgent(llm=mock_llm, searcher=searcher)

        results = await agent.recall("user likes dark mode")

        mock_llm.complete_json.assert_called_once()
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_recall_fallback_on_empty_queries(self, mock_llm, memory_store, noop_embedder):
        """When LLM returns no queries, use the original content."""
        mock_llm.complete_json.return_value = {"queries": []}
        searcher = MemorySearcher(store=memory_store, embedder=noop_embedder)
        agent = RecallAgent(llm=mock_llm, searcher=searcher)

        results = await agent.recall("test content")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_recall_excludes_hippocampus_partition(self, mock_llm, memory_store, noop_embedder):
        """Recalled memories should not include hebb partition."""
        # Create memories in different partitions
        await memory_store.create(
            MemoryCreate(content="in hebb", partition_id="mem_hippocampus"),
        )
        await memory_store.create(
            MemoryCreate(content="in semantic", partition_id="mem_semantic"),
        )

        mock_llm.complete_json.return_value = {"queries": ["test"]}
        searcher = MemorySearcher(store=memory_store, embedder=noop_embedder)
        agent = RecallAgent(llm=mock_llm, searcher=searcher)

        results = await agent.recall("test")
        for mem in results:
            assert mem.partition_id != "mem_hippocampus"

    @pytest.mark.asyncio
    async def test_recall_handles_llm_error(self, mock_llm, memory_store, noop_embedder):
        """When LLM fails, recall should propagate the error."""
        mock_llm.complete_json.side_effect = Exception("LLM down")
        searcher = MemorySearcher(store=memory_store, embedder=noop_embedder)
        agent = RecallAgent(llm=mock_llm, searcher=searcher)

        with pytest.raises(Exception, match="LLM down"):
            await agent.recall("test")
