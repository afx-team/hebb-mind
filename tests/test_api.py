"""E2E tests for the FastAPI server — core flow with mocked embedder."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class MockEmbedder:
    """Mock embedder that returns random vectors (no model download needed)."""

    @property
    def dimension(self) -> int:
        return 384

    async def embed(self, text: str) -> list[float]:
        random.seed(hash(text) % (2**31))
        return [random.gauss(0, 1) for _ in range(384)]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]


async def _mock_create_embedder(settings):
    return MockEmbedder()


@pytest.fixture
def client(tmp_path: Path):
    """Create a test client with temporary DB and mocked embedder."""
    config_path = tmp_path / "hippocampus.json"
    config_path.write_text(json.dumps({
        "db_path": str(tmp_path / "test.db"),
        "kg_path": str(tmp_path / "test_kg.json"),
        "port": 8321,
    }))

    with patch("hippocampus.config.loader.find_config_file", return_value=config_path), \
         patch("hippocampus.embedding.factory.create_embedder", side_effect=_mock_create_embedder):
        from hippocampus.server.app import create_app
        app = create_app()
        with TestClient(app) as c:
            yield c


class TestHealthEndpoints:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_status(self, client: TestClient):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "scheduler" in data


class TestPartitionEndpoints:
    def test_list_partitions(self, client: TestClient):
        resp = client.get("/api/v1/partitions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5
        ids = {p["id"] for p in data}
        assert "mem_hippocampus" in ids
        assert "mem_semantic" in ids

    def test_create_partition(self, client: TestClient):
        resp = client.post("/api/v1/partitions", json={
            "id": "mem_custom",
            "name": "Custom Partition",
            "description": "test",
        })
        assert resp.status_code == 201
        assert resp.json()["id"] == "mem_custom"

    def test_update_partition(self, client: TestClient):
        resp = client.patch("/api/v1/partitions/mem_hippocampus", json={
            "description": "Updated description",
        })
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    def test_delete_system_partition_forbidden(self, client: TestClient):
        resp = client.delete("/api/v1/partitions/mem_hippocampus")
        assert resp.status_code == 403

    def test_delete_custom_partition(self, client: TestClient):
        client.post("/api/v1/partitions", json={"id": "mem_temp", "name": "Temp"})
        resp = client.delete("/api/v1/partitions/mem_temp")
        assert resp.status_code == 204


class TestMemoryEndpoints:
    def test_create_memory(self, client: TestClient):
        resp = client.post("/api/v1/memories", json={
            "content": "User prefers dark mode",
            "partition_id": "mem_hippocampus",
            "tags": ["preference", "ui"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "User prefers dark mode"
        assert data["partition_id"] == "mem_hippocampus"
        assert "id" in data

    def test_get_memory(self, client: TestClient):
        create_resp = client.post("/api/v1/memories", json={"content": "test memory"})
        memory_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/memories/{memory_id}")
        assert resp.status_code == 200
        assert resp.json()["content"] == "test memory"

    def test_list_memories(self, client: TestClient):
        client.post("/api/v1/memories", json={"content": "a"})
        client.post("/api/v1/memories", json={"content": "b"})
        resp = client.get("/api/v1/memories")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    def test_update_memory(self, client: TestClient):
        create_resp = client.post("/api/v1/memories", json={"content": "original"})
        memory_id = create_resp.json()["id"]
        resp = client.patch(f"/api/v1/memories/{memory_id}", json={"content": "updated"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "updated"

    def test_delete_memory(self, client: TestClient):
        create_resp = client.post("/api/v1/memories", json={"content": "to delete"})
        memory_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/memories/{memory_id}")
        assert resp.status_code == 204
        resp = client.get(f"/api/v1/memories/{memory_id}")
        assert resp.status_code == 404

    def test_batch_create(self, client: TestClient):
        resp = client.post("/api/v1/memories/batch", json=[
            {"content": "memory 1"},
            {"content": "memory 2"},
            {"content": "memory 3"},
        ])
        assert resp.status_code == 201
        assert len(resp.json()) == 3

    def test_filter_by_partition(self, client: TestClient):
        client.post("/api/v1/memories", json={"content": "a", "partition_id": "mem_hippocampus"})
        client.post("/api/v1/memories", json={"content": "b", "partition_id": "mem_semantic"})
        resp = client.get("/api/v1/memories?partition_id=mem_hippocampus")
        for item in resp.json()["items"]:
            assert item["partition_id"] == "mem_hippocampus"


class TestSearchEndpoint:
    def test_search(self, client: TestClient):
        client.post("/api/v1/memories", json={"content": "Python is a programming language"})
        client.post("/api/v1/memories", json={"content": "The sky is blue"})
        resp = client.post("/api/v1/search", json={"query": "programming language"})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) > 0


class TestGraphEndpoints:
    def test_empty_tags(self, client: TestClient):
        resp = client.get("/api/v1/graph/tags")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_export(self, client: TestClient):
        resp = client.get("/api/v1/graph/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data


class TestAdminEndpoints:
    def test_stats(self, client: TestClient):
        resp = client.get("/api/v1/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "partitions" in data
        assert "total_memories" in data
        assert "graph" in data
        assert "scheduler" in data
