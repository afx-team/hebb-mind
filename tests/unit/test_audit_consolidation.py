"""Audit regression tests for lane E (consolidation / forgetting / graph).

Covers the safety fixes from the 2026-06-07 core system audit:

* forgetting F1 / consolidation F2 — importance 0 and brand-new memories are
  not deleted on the very next sweep (TTL floor + grace window).
* consolidation F4 — an empty/garbled LLM decision must not delete the source.
* consolidation F8 — a conflict ``update`` re-embeds the updated content and
  only targets ids that were actually recalled.
* LLM config F3 — consolidation no-ops cleanly when ``llm_model`` is unset.
* recall F4 / C6 — ``search_tags`` matches per-token, not whole-query substring.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hebb.agents.consolidation_agent import ConsolidationAgent
from hebb.agents.recall_agent import RecallAgent
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import Memory, MemoryCreate
from hebb.retrieval.searcher import MemorySearcher
from hebb.scheduler.consolidation_job import run_consolidation
from hebb.scheduler.forgetting_job import (
    DEFAULT_MIN_RETENTION_DAYS,
    compute_expires_at,
    forget_idle_days,
)

# Representative parameter set (the global user-partition defaults).
_PARAMS = dict(half_life_days=60.0, k_importance=2.0, k_access=1.5, threshold=0.3)


# --------------------------------------------------------------------------- #
# Forgetting: importance 0 is not a delete signal + retention floor (F1 / F2)
# --------------------------------------------------------------------------- #
class TestForgettingSafety:
    def test_importance_zero_not_immediately_expired(self) -> None:
        """importance_score == 0 adds no boost, but must NOT collapse the lifetime."""
        now = datetime.now(timezone.utc)
        mem = Memory(
            id="imp0",
            content="zero importance fact",
            last_accessed_at=now,
            created_at=now,
            access_count=5,
            importance_score=0.0,
        )
        expires = compute_expires_at(mem, **_PARAMS)
        assert expires > now

    def test_higher_importance_lives_longer(self) -> None:
        """importance 0 (no boost) must expire no later than a higher-importance peer."""
        now = datetime.now(timezone.utc)
        imp0 = Memory(id="i0", content="x", last_accessed_at=now, created_at=now, access_count=5, importance_score=0.0)
        imp8 = Memory(id="i8", content="x", last_accessed_at=now, created_at=now, access_count=5, importance_score=8.0)
        assert compute_expires_at(imp8, **_PARAMS) > compute_expires_at(imp0, **_PARAMS)

    def test_retention_floored_at_min(self) -> None:
        """A pathological tiny half-life / high threshold can't delete instantly."""
        idle = forget_idle_days(0.1, 0.95, min_retention_days=DEFAULT_MIN_RETENTION_DAYS)
        assert idle >= DEFAULT_MIN_RETENTION_DAYS

    def test_fresh_memory_survives_well_past_one_sweep(self) -> None:
        """A just-written low-value memory still has a long retained lifetime."""
        now = datetime.now(timezone.utc)
        mem = Memory(
            id="fresh",
            content="just written",
            last_accessed_at=now,
            created_at=now,
            access_count=0,
            importance_score=0.0,  # worst case: zero importance, never accessed
        )
        expires = compute_expires_at(mem, **_PARAMS)
        # 60-day half-life, threshold 0.3 → ~72 days; comfortably past a week.
        assert expires > now + timedelta(days=7)


# --------------------------------------------------------------------------- #
# Graph: per-token search_tags (recall F4 / C6)
# --------------------------------------------------------------------------- #
class TestSearchTagsTokenization:
    def _kg(self, tmp_path: Path) -> KnowledgeGraph:
        kg = KnowledgeGraph(tmp_path / "kg.json")
        kg.update_from_tags(["python", "asyncio", "database"], "m1")
        kg.update_from_tags(["dark-mode"], "m2")
        return kg

    def test_multiword_query_matches_a_token(self, tmp_path: Path) -> None:
        kg = self._kg(tmp_path)
        # Whole-query substring would never match any single tag here.
        results = kg.search_tags("how do I use python asyncio")
        ids = {n.id for n in results}
        assert "python" in ids
        assert "asyncio" in ids

    def test_label_token_match(self, tmp_path: Path) -> None:
        kg = self._kg(tmp_path)
        results = kg.search_tags("enable dark mode please")
        # 'dark-mode' tokenizes to {'dark', 'mode'} and matches 'dark'/'mode'.
        assert any(n.id == "dark-mode" for n in results)

    def test_empty_query_returns_empty(self, tmp_path: Path) -> None:
        kg = self._kg(tmp_path)
        assert kg.search_tags("   ") == []

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        kg = self._kg(tmp_path)
        assert kg.search_tags("quantum chromodynamics") == []


# --------------------------------------------------------------------------- #
# Consolidation: empty-output guard + conflict re-embed (F4 / F8)
# --------------------------------------------------------------------------- #
def _make_agent(
    mock_llm, memory_store, partition_store, embedder, tmp_path
) -> tuple[ConsolidationAgent, KnowledgeGraph]:
    kg = KnowledgeGraph(tmp_path / "kg.json")
    recall_agent = RecallAgent(
        llm=mock_llm,
        searcher=MemorySearcher(store=memory_store, embedder=embedder),
    )
    agent = ConsolidationAgent(
        llm=mock_llm,
        recall_agent=recall_agent,
        memory_store=memory_store,
        partition_store=partition_store,
        knowledge_graph=kg,
        embedder=embedder,
    )
    return agent, kg


class TestConsolidationEmptyOutputGuard:
    @pytest.mark.asyncio
    async def test_empty_content_keeps_source(
        self, mock_llm, memory_store, partition_store, noop_embedder, tmp_path
    ) -> None:
        """An empty consolidated_content must NOT delete the source memory."""
        mem = await memory_store.create(
            MemoryCreate(content="A real fact worth keeping", partition_id="mem_hippocampus"),
        )
        mock_llm.complete_json.side_effect = [
            # RecallAgent.recall -> query generation
            {"queries": ["fact"]},
            # ConsolidationAgent -> empty/garbled decision (no usable content)
            {
                "target_partition": "mem_semantic",
                "consolidated_content": "   ",
                "importance_score": 5.0,
                "tags": [],
                "conflicts": [],
            },
        ]
        agent, _ = _make_agent(mock_llm, memory_store, partition_store, noop_embedder, tmp_path)

        result = await agent.consolidate_memory(mem)

        # Source must still exist — no silent data loss.
        assert await memory_store.get(mem.id) is not None
        # No replacement memory was written into the target partition.
        assert await memory_store.get_by_partition("mem_semantic") == []
        assert result.target_partition == "kept"

    @pytest.mark.asyncio
    async def test_empty_content_keeps_source_in_batch_path(
        self, mock_llm, memory_store, partition_store, noop_embedder, tmp_path
    ) -> None:
        """The batch standalone path (_consolidate_one) also keeps the source."""
        mem = await memory_store.create(
            MemoryCreate(content="Another keepable fact", partition_id="mem_hippocampus"),
        )
        mock_llm.complete_json.side_effect = [
            {"queries": ["fact"]},
            {
                "target_partition": "mem_semantic",
                "consolidated_content": "",
                "importance_score": 5.0,
                "tags": [],
                "conflicts": [],
            },
        ]
        agent, _ = _make_agent(mock_llm, memory_store, partition_store, noop_embedder, tmp_path)

        await agent.consolidate_batch(concurrency=1)

        assert await memory_store.get(mem.id) is not None
        assert await memory_store.get_by_partition("mem_semantic") == []


class TestConflictUpdateReembeds:
    @pytest.mark.asyncio
    async def test_conflict_update_reembeds_and_scopes_to_recalled(
        self, mock_llm, memory_store, partition_store, noop_embedder, tmp_path
    ) -> None:
        """conflict update re-embeds the new text and ignores non-recalled ids."""
        # An existing long-term memory that the LLM "recalls" and updates.
        existing = await memory_store.create(
            MemoryCreate(content="User likes tea", partition_id="mem_preference"),
            embedding=await noop_embedder.embed("User likes tea"),
        )
        src = await memory_store.create(
            MemoryCreate(content="Actually user prefers coffee now", partition_id="mem_hippocampus"),
        )

        # Spy on update_embedding to confirm the re-embed fires for the right id.
        reembedded: list[str] = []
        original_update_embedding = memory_store.update_embedding

        async def _spy(memory_id: str, embedding: list[float]) -> None:
            reembedded.append(memory_id)
            await original_update_embedding(memory_id, embedding)

        memory_store.update_embedding = _spy  # type: ignore[method-assign]

        mock_llm.complete_json.side_effect = [
            # RecallAgent.recall -> query generation (returns the existing mem)
            {"queries": ["tea coffee preference"]},
            # ConsolidationAgent decision: update the recalled id AND a bogus id
            {
                "target_partition": "mem_preference",
                "consolidated_content": "User prefers coffee.",
                "importance_score": 7.0,
                "tags": ["preference"],
                "conflicts": [
                    {"memory_id": existing.id, "resolution": "update"},
                    {"memory_id": "mem_does_not_exist", "resolution": "update"},
                ],
            },
        ]
        agent, _ = _make_agent(mock_llm, memory_store, partition_store, noop_embedder, tmp_path)

        result = await agent.consolidate_memory(src)

        # Recalled id was updated AND re-embedded; bogus id was ignored.
        assert reembedded == [existing.id]
        assert result.conflicts_resolved == 1
        updated = await memory_store.get(existing.id)
        assert updated is not None
        assert updated.content == "User prefers coffee."


# --------------------------------------------------------------------------- #
# LLM config F3: consolidation no-ops cleanly when llm_model is unset
# --------------------------------------------------------------------------- #
class TestConsolidationLLMModelGuard:
    @pytest.mark.asyncio
    async def test_run_consolidation_skips_without_llm_model(
        self, settings, memory_store, partition_store, noop_embedder, tmp_path
    ) -> None:
        """No llm_model -> run_consolidation returns [] without calling litellm."""
        settings.llm_model = None
        kg = KnowledgeGraph(tmp_path / "kg.json")

        # Seed a memory so an unguarded path would actually try to consolidate.
        await memory_store.create(
            MemoryCreate(content="should not be touched", partition_id="mem_hippocampus"),
        )

        results = await run_consolidation(
            memory_store=memory_store,
            partition_store=partition_store,
            knowledge_graph=kg,
            embedder=noop_embedder,
            settings=settings,
        )
        assert results == []
