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


def test_cached_but_unloadable_falls_through_to_download(client: TestClient) -> None:
    """An interrupted/corrupt cache (config present, weights missing) must not
    dead-end on the load error — it should re-download instead of returning a
    failure the user can't act on."""

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("no file named model.safetensors, or pytorch_model.bin, found in directory")

    with patch("hebb.embedding.local.is_model_cached", return_value=True), patch(
        "hebb.embedding.local.LocalEmbedder", side_effect=_boom
    ), patch("hebb.embedding.catalog.prefetch_model") as prefetch:
        prefetch.return_value = Path("/tmp/fake-model")
        resp = client.post(
            "/api/v1/admin/config/test-embedding",
            json={"provider": "local", "model": "BAAI/bge-m3"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["async"] is True
    assert body["success"] is True
    assert isinstance(body["task_id"], str) and body["task_id"]


def test_invalid_provider_rejected(client: TestClient) -> None:
    """Literal['local','api'] should make pydantic reject typos."""
    resp = client.post(
        "/api/v1/admin/config/test-embedding",
        json={"provider": "Local", "model": "x"},  # capital L → invalid
    )
    assert resp.status_code == 422


def test_custom_http_mode_reports_dimension(client: TestClient) -> None:
    """API + custom mode probes the user-defined endpoint and returns its dimension."""

    class FakeEmbedder:
        def __init__(self, **_: object) -> None: ...

        async def embed(self, text: str) -> list[float]:
            return [0.1] * 7

    with patch("hebb.embedding.http_custom.CustomHttpEmbedder", FakeEmbedder):
        resp = client.post(
            "/api/v1/admin/config/test-embedding",
            json={
                "provider": "api",
                "api_mode": "custom",
                "http_method": "POST",
                "http_url": "https://example.com/embed",
                "http_headers": "{}",
                "http_body": '{"input": {{input}}}',
                "http_response_path": "data.*.embedding",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["async"] is False
    assert body["dimension"] == 7


def test_custom_http_mode_requires_url(client: TestClient) -> None:
    """Custom mode without a URL is a friendly error, not a 500."""
    resp = client.post(
        "/api/v1/admin/config/test-embedding",
        json={"provider": "api", "api_mode": "custom", "http_body": '{"input": {{input}}}'},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is False
    assert "URL is required" in body["error"]
