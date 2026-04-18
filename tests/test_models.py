"""Tests for Pydantic data models."""

from hippocampus.models.memory import Memory, MemoryCreate, MemoryQuery, MemoryUpdate
from hippocampus.models.partition import Partition, PartitionCreate, PartitionUpdate
from hippocampus.models.graph import TagNode, TagEdge, KnowledgeGraphState
from hippocampus.models.common import PaginatedResponse


class TestMemoryModels:
    def test_memory_create_defaults(self):
        m = MemoryCreate(content="test content")
        assert m.partition_id == "mem_hippocampus"
        assert m.importance_score == 5.0
        assert m.tags == []
        assert m.metadata == {}

    def test_memory_create_custom(self):
        m = MemoryCreate(
            content="user likes coffee",
            partition_id="mem_preference",
            importance_score=8.0,
            tags=["coffee", "preference"],
        )
        assert m.partition_id == "mem_preference"
        assert m.importance_score == 8.0
        assert len(m.tags) == 2

    def test_memory_has_uuid(self):
        m = Memory(content="test")
        assert len(m.id) == 36  # UUID format

    def test_memory_query_defaults(self):
        q = MemoryQuery(query="search term")
        assert q.top_k == 10
        assert q.weight_recency == 1.0

    def test_memory_update_partial(self):
        u = MemoryUpdate(content="new content")
        assert u.content == "new content"
        assert u.importance_score is None
        assert u.tags is None


class TestPartitionModels:
    def test_partition_create_validation(self):
        p = PartitionCreate(id="mem_custom_test", name="Custom Test")
        assert p.enabled is True

    def test_partition_create_invalid_id(self):
        import pytest
        with pytest.raises(Exception):
            PartitionCreate(id="invalid", name="Bad ID")

    def test_partition_update_partial(self):
        u = PartitionUpdate(description="new desc")
        assert u.name is None
        assert u.description == "new desc"


class TestGraphModels:
    def test_tag_node(self):
        t = TagNode(id="python", label="Python")
        assert t.weight == 1.0
        assert t.memory_ids == []

    def test_knowledge_graph_state_serialization(self):
        state = KnowledgeGraphState(
            nodes=[TagNode(id="a", label="A")],
            edges=[TagEdge(source="a", target="b")],
        )
        json_str = state.model_dump_json()
        restored = KnowledgeGraphState.model_validate_json(json_str)
        assert len(restored.nodes) == 1
        assert len(restored.edges) == 1


class TestCommonModels:
    def test_paginated_response(self):
        r = PaginatedResponse[str](items=["a", "b"], total=10, offset=0, limit=2)
        assert len(r.items) == 2
        assert r.total == 10
