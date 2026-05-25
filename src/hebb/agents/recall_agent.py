"""Recall Agent — Agentic RAG for finding related historical memories."""

from __future__ import annotations

import logging

from hebb.agents.llm_client import LLMClient
from hebb.agents.prompts import RECALL_SYSTEM_PROMPT, RECALL_USER_TEMPLATE
from hebb.models.memory import Memory, MemoryQuery
from hebb.retrieval.searcher import MemorySearcher

logger = logging.getLogger(__name__)


class RecallAgent:
    """Generates search queries via LLM and retrieves related memories."""

    def __init__(self, llm: LLMClient, searcher: MemorySearcher) -> None:
        self.llm = llm
        self.searcher = searcher

    async def recall(
        self,
        memory_content: str,
        exclude_partition: str | None = "mem_hippocampus",
        top_k: int = 10,
    ) -> list[Memory]:
        """
        Agentic RAG:
        1. Ask LLM to generate search queries
        2. Execute each query via MemorySearcher
        3. Deduplicate and return
        """
        # Step 1: Generate queries
        messages = [
            {"role": "system", "content": RECALL_SYSTEM_PROMPT},
            {"role": "user", "content": RECALL_USER_TEMPLATE.format(content=memory_content)},
        ]
        result = await self.llm.complete_json(messages, temperature=0.3)
        queries = result.get("queries", [memory_content])

        if not queries:
            queries = [memory_content]

        # Step 2: Search with each query
        seen_ids: set[str] = set()
        all_memories: list[Memory] = []

        for query_text in queries[:3]:  # limit to 3 queries
            try:
                response = await self.searcher.search(
                    MemoryQuery(query=query_text, top_k=top_k),
                )
                for sr in response.results:
                    if sr.memory.id not in seen_ids:
                        if exclude_partition and sr.memory.partition_id == exclude_partition:
                            continue
                        seen_ids.add(sr.memory.id)
                        all_memories.append(sr.memory)
            except Exception:
                logger.warning("Recall search failed for query: %s", query_text, exc_info=True)

        return all_memories[:top_k]
