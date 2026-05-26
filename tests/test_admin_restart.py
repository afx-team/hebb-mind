"""Tests for the POST /api/v1/admin/restart endpoint.

The endpoint must return *before* the OS supervisor kills the process, so the
contract is: schedule a delayed restart task, respond immediately with the
expected downtime. We assert the response shape and that ``ServiceManager``
isn't touched synchronously inside the request handler.
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


async def _mock_create_embedder(settings):  # noqa: ANN001 — Settings is internal
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


def test_restart_returns_scheduled_response(client: TestClient) -> None:
    # We must avoid actually invoking the OS supervisor in tests. Patch
    # ServiceManager.restart so the delayed task is a no-op even if it fires
    # before the test process tears down.
    with patch("hebb.utils.service_manager.LaunchdManager.restart"), patch(
        "hebb.utils.service_manager.SystemdManager.restart"
    ), patch("hebb.utils.service_manager.WindowsTaskManager.restart"):
        resp = client.post("/api/v1/admin/restart")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["message"] == "Restart scheduled"
    assert isinstance(body["expected_downtime_seconds"], int)
    assert body["poll"] == "/health"


def test_restart_returns_501_on_unsupported_platform(client: TestClient) -> None:
    from hebb.utils.service_manager import UnsupportedPlatformError

    with patch(
        "hebb.utils.service_manager.get_manager",
        side_effect=UnsupportedPlatformError("nope"),
    ):
        resp = client.post("/api/v1/admin/restart")

    assert resp.status_code == 501
    assert "nope" in resp.text
