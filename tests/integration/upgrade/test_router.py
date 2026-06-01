"""Tests for /api/v1/admin/upgrade endpoints — GET state + POST /check."""

from __future__ import annotations

import json
import random
from pathlib import Path
from unittest.mock import AsyncMock, patch

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


def test_get_returns_default_state_when_no_file(client: TestClient) -> None:
    resp = client.get("/api/v1/admin/upgrade")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is False
    assert body["current_version"] == ""
    assert body["mode"] == "notify"  # default


def test_post_check_triggers_refresh(client: TestClient) -> None:
    with (
        patch("hebb.upgrade.checker.__version__", "0.1.3"),
        patch(
            "hebb.upgrade.checker.fetch_latest_version",
            new=AsyncMock(return_value="0.2.0"),
        ),
    ):
        resp = client.post("/api/v1/admin/upgrade/check")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["latest_version"] == "0.2.0"
    assert body["available"] is True
    assert body["current_version"] == "0.1.3"


def test_post_check_refused_when_mode_off(client: TestClient) -> None:
    # Flip mode on the live settings object the app already holds.
    client.app.state.settings.auto_upgrade_mode = "off"
    resp = client.post("/api/v1/admin/upgrade/check")
    assert resp.status_code == 409
    assert "disabled" in resp.text.lower()


def test_get_reflects_persisted_state(tmp_path: Path, client: TestClient) -> None:
    # Write a known state to disk via the live settings.home_dir, then GET.
    from hebb.upgrade import state as upgrade_state

    home = client.app.state.settings.home_dir
    assert home is not None
    upgrade_state.save(
        home,
        upgrade_state.UpgradeState(
            current_version="0.1.3",
            latest_version="0.1.9",
            available=True,
            checked_at="2026-05-27T12:00:00+00:00",
        ),
    )
    resp = client.get("/api/v1/admin/upgrade")
    body = resp.json()
    assert body["latest_version"] == "0.1.9"
    assert body["available"] is True
