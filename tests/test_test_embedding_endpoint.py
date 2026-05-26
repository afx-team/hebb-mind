"""Tests for POST /api/v1/admin/config/test-embedding async/sync dispatch."""

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


async def _mock_create_embedder(settings):  # noqa: ANN001
    return MockEmbedder()


@pytest.fixture
def client(tmp_path: Path):
    config_path = tmp_path / "hebb.json"
    config_path.write_text(json.dumps({"port": 8321}))
    with (
        patch("hebb.config.loader.find_config_file", return_value=config_path),
        patch("hebb.embedding.factory.create_embedder", side_effect=_mock_create_embedder),
    ):
        from hebb.server.app import create_app

        app = create_app()
        with TestClient(app) as c:
            yield c


def test_local_uncached_returns_task_id(client: TestClient) -> None:
    """When the model isn't on disk yet, the endpoint must return a task_id
    and never block the request handler on the download."""

    with patch("hebb.embedding.local.is_model_cached", return_value=False), patch(
        "hebb.embedding.catalog.prefetch_model"
    ) as prefetch:
        # Make prefetch a no-op so the background task completes quickly.
        prefetch.return_value = Path("/tmp/fake-model")
        resp = client.post(
            "/api/v1/admin/config/test-embedding",
            json={"provider": "local", "model": "BAAI/bge-large-en-v1.5"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["async"] is True
    assert body["success"] is True
    assert isinstance(body["task_id"], str) and body["task_id"]


def test_status_endpoint_returns_404_for_unknown_task(client: TestClient) -> None:
    resp = client.get("/api/v1/admin/config/test-embedding/status/does-not-exist")
    assert resp.status_code == 404


def test_local_cached_runs_sync(client: TestClient) -> None:
    """Cached models skip the task table and answer in one round-trip."""

    class FakeEmbedder:
        @property
        def dimension(self) -> int:
            return 1024

        async def embed(self, text: str) -> list[float]:
            return [0.1] * 1024

    with patch("hebb.embedding.local.is_model_cached", return_value=True), patch(
        "hebb.embedding.local.LocalEmbedder", return_value=FakeEmbedder()
    ):
        resp = client.post(
            "/api/v1/admin/config/test-embedding",
            json={"provider": "local", "model": "BAAI/bge-large-en-v1.5"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["async"] is False
    assert body["success"] is True
    assert body["dimension"] == 1024


def test_invalid_provider_rejected(client: TestClient) -> None:
    """Literal['local','api'] should make pydantic reject typos."""
    resp = client.post(
        "/api/v1/admin/config/test-embedding",
        json={"provider": "Local", "model": "x"},  # capital L → invalid
    )
    assert resp.status_code == 422
