"""Tests for knowledge graph."""

from pathlib import Path

import pytest

from hebb.graph.knowledge_graph import KnowledgeGraph


class TestKnowledgeGraph:
    @pytest.fixture
    def kg(self, tmp_path: Path) -> KnowledgeGraph:
        return KnowledgeGraph(tmp_path / "test_kg.json")

    def test_add_tag(self, kg: KnowledgeGraph):
        kg.add_tag("python", "mem1")
        tag = kg.get_tag("python")
        assert tag is not None
        assert tag.id == "python"
        assert "mem1" in tag.memory_ids

    def test_add_tag_twice(self, kg: KnowledgeGraph):
        kg.add_tag("python", "mem1")
        kg.add_tag("python", "mem2")
        tag = kg.get_tag("python")
        assert tag is not None
        assert len(tag.memory_ids) == 2
        assert tag.weight == 2.0

    def test_update_from_tags(self, kg: KnowledgeGraph):
        kg.update_from_tags(["python", "ml", "ai"], "mem1")
        assert kg.get_tag("python") is not None
        assert kg.get_tag("ml") is not None
        assert kg.get_tag("ai") is not None
        # Co-occurrence edges
        assert kg.graph.has_edge("python", "ml")
        assert kg.graph.has_edge("python", "ai")
        assert kg.graph.has_edge("ml", "ai")

    def test_query_neighbors(self, kg: KnowledgeGraph):
        kg.update_from_tags(["python", "ml"], "mem1")
        kg.update_from_tags(["ml", "deep_learning"], "mem2")

        result = kg.query_neighbors("python", depth=1)
        node_ids = {n.id for n in result.nodes}
        assert "python" in node_ids
        assert "ml" in node_ids

    def test_search_path(self, kg: KnowledgeGraph):
        kg.update_from_tags(["python", "ml"], "mem1")
        kg.update_from_tags(["ml", "deep_learning"], "mem2")

        result = kg.search_path("python", "deep_learning")
        assert result.paths is not None
        assert len(result.paths) == 1
        assert result.paths[0] == ["python", "ml", "deep_learning"]

    def test_search_tags(self, kg: KnowledgeGraph):
        kg.add_tag("python", "mem1")
        kg.add_tag("python3", "mem2")
        kg.add_tag("java", "mem3")

        results = kg.search_tags("python")
        assert len(results) == 2

    def test_save_and_load(self, kg: KnowledgeGraph):
        kg.update_from_tags(["a", "b", "c"], "mem1")
        kg.save()

        # Load fresh
        kg2 = KnowledgeGraph(kg.path)
        assert kg2.get_tag("a") is not None
        assert kg2.get_tag("b") is not None
        assert kg2.graph.has_edge("a", "b")

    def test_export(self, kg: KnowledgeGraph):
        kg.update_from_tags(["x", "y"], "mem1")
        state = kg.export()
        assert len(state.nodes) == 2
        assert len(state.edges) == 1

    def test_remove_memory_from_tags(self, kg: KnowledgeGraph):
        kg.add_tag("python", "mem1")
        kg.add_tag("python", "mem2")
        kg.remove_memory_from_tags("mem1")
        tag = kg.get_tag("python")
        assert tag is not None
        assert "mem1" not in tag.memory_ids
        assert "mem2" in tag.memory_ids
