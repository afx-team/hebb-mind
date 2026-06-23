"""Integration tests for the per-partition forgetting router.

Exercises GET/PUT/DELETE /api/v1/admin/forgetting and the non-destructive
/forgetting/{id}/preview against a real app (mocked embedder, temp hebb.json).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class MockEmbedder:
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
    config_path = tmp_path / "hebb.json"
    # Seed a real default config so update_forgetting_overrides has a file to RMW.
    from hebb.config.loader import create_default_config

    create_default_config(config_path)

    with (
        patch("hebb.config.loader.find_config_file", return_value=config_path),
        patch("hebb.embedding.factory.create_embedder", side_effect=_mock_create_embedder),
    ):
        from hebb.server.app import create_app

        app = create_app()
        with TestClient(app) as c:
            c.hebb_config_path = config_path  # type: ignore[attr-defined]
            yield c


def _first_swept_partition(client: TestClient) -> str:
    cfg = client.get("/api/v1/admin/forgetting").json()
    return next(p["id"] for p in cfg["partitions"] if p["swept"])


class TestForgettingConfig:
    def test_get_config_shape(self, client: TestClient):
        resp = client.get("/api/v1/admin/forgetting")
        assert resp.status_code == 200
        data = resp.json()
        assert data["global_half_life_days"] == 60.0
        assert data["global_k_importance"] == 2.0
        assert data["global_k_access"] == 1.5
        assert data["global_threshold"] == 0.3
        assert data["min_retention_days"] == 1.0
        assert data["partitions"]
        # HIPPOCAMPUS is present but never swept.
        hippo = next(p for p in data["partitions"] if p["id"] == "mem_hippocampus")
        assert hippo["swept"] is False
        assert hippo["effective"]["enabled"] is False

    def test_put_and_get_override(self, client: TestClient):
        pid = _first_swept_partition(client)
        resp = client.put(f"/api/v1/admin/forgetting/{pid}", json={"half_life_days": 720.0, "enabled": True})
        assert resp.status_code == 200
        entry = resp.json()
        assert entry["override"]["half_life_days"] == 720.0
        assert entry["effective"]["half_life_days"] == 720.0
        # threshold was not overridden → inherits the region/global baseline.
        assert entry["effective"]["threshold"] == entry["inherited"]["threshold"]

        # Persisted to hebb.json on disk.
        on_disk = json.loads(client.hebb_config_path.read_text())  # type: ignore[attr-defined]
        assert on_disk["forgetting_overrides"][pid]["half_life_days"] == 720.0

        # Reflected in a fresh GET.
        cfg = client.get("/api/v1/admin/forgetting").json()
        entry2 = next(p for p in cfg["partitions"] if p["id"] == pid)
        assert entry2["override"]["half_life_days"] == 720.0

    def test_disable_then_clear(self, client: TestClient):
        pid = _first_swept_partition(client)
        client.put(f"/api/v1/admin/forgetting/{pid}", json={"enabled": False})
        cfg = client.get("/api/v1/admin/forgetting").json()
        entry = next(p for p in cfg["partitions"] if p["id"] == pid)
        assert entry["override"]["enabled"] is False
        assert entry["effective"]["enabled"] is False

        # Clear → back to inherit (no override, enabled again).
        resp = client.delete(f"/api/v1/admin/forgetting/{pid}")
        assert resp.status_code == 200
        assert resp.json()["override"] is None
        on_disk = json.loads(client.hebb_config_path.read_text())  # type: ignore[attr-defined]
        assert pid not in on_disk.get("forgetting_overrides", {})

    def test_put_unknown_partition_404(self, client: TestClient):
        resp = client.put("/api/v1/admin/forgetting/mem_does_not_exist", json={"enabled": True})
        assert resp.status_code == 404

    def test_put_rejects_out_of_range(self, client: TestClient):
        pid = _first_swept_partition(client)
        # half_life_days must be > 0; threshold must be in (0, 1).
        assert client.put(f"/api/v1/admin/forgetting/{pid}", json={"half_life_days": -5}).status_code == 422
        assert client.put(f"/api/v1/admin/forgetting/{pid}", json={"threshold": 1.5}).status_code == 422


class TestForgettingPreview:
    def _make_memory(self, client: TestClient, partition_id: str) -> None:
        resp = client.post(
            "/api/v1/memories",
            json={"content": "a tunable memory", "partition_id": partition_id, "importance_score": 5.0},
        )
        assert resp.status_code in (200, 201)

    def test_preview_structure(self, client: TestClient):
        pid = _first_swept_partition(client)
        self._make_memory(client, pid)
        resp = client.post(f"/api/v1/admin/forgetting/{pid}/preview", json={"enabled": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["swept"] is True
        assert data["total"] >= 1
        assert data["would_forget"] + data["would_keep"] == data["total"]
        # A freshly-written memory (idle ≈ 0) has full retention → not forgotten.
        assert data["would_forget"] == 0

    def test_preview_disabled_forgets_nothing(self, client: TestClient):
        pid = _first_swept_partition(client)
        self._make_memory(client, pid)
        resp = client.post(f"/api/v1/admin/forgetting/{pid}/preview", json={"enabled": False})
        data = resp.json()
        assert data["swept"] is False
        assert data["would_forget"] == 0

    def test_preview_hippocampus_never_swept(self, client: TestClient):
        resp = client.post("/api/v1/admin/forgetting/mem_hippocampus/preview", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["swept"] is False


class TestForgettingRecords:
    def test_runs_endpoint_shape(self, client: TestClient):
        resp = client.get("/api/v1/admin/forgetting/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json()["runs"], list)

    def test_manual_forget_records_a_run(self, client: TestClient):
        # Seed one memory so the sweep has a partition to scan.
        pid = _first_swept_partition(client)
        client.post(
            "/api/v1/memories",
            json={"content": "record me", "partition_id": pid, "importance_score": 5.0},
        )
        assert client.post("/api/v1/admin/forget").status_code == 200

        runs = client.get("/api/v1/admin/forgetting/runs").json()["runs"]
        assert runs, "a manual forget should have been recorded"
        latest = runs[0]  # most-recent first
        assert latest["trigger"] == "manual"
        assert latest["status"] == "done"
        # The seeded memory was just written (full retention) → scanned, not deleted.
        assert latest["scanned"] >= 1
        assert latest["deleted"] == 0
        assert latest["partitions_swept"] >= 1
