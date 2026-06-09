"""E2E test for the boot-time consolidation catch-up after an interrupted run.

Simulates the real "system stopped mid-consolidation, then restarted" path:
a manifest left with a ``running`` run + working memories still pending must,
on the next server start, be reaped to ``interrupted`` and trigger a scheduled
catch-up so the inbox is resumed ("下次继续") instead of waiting a full day.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class _MockEmbedder:
    @property
    def dimension(self) -> int:
        return 384

    async def embed(self, text: str) -> list[float]:
        random.seed(hash(text) % (2**31))
        return [random.gauss(0, 1) for _ in range(384)]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]


async def _mock_create_embedder(settings):
    return _MockEmbedder()


def _write_config(tmp_path: Path, *, with_llm: bool) -> Path:
    config = {"port": 8321}
    if with_llm:
        # A configured LLM is required for consolidation (and the catch-up).
        config["llm_model"] = "openai/gpt-4o-mini"
        config["llm_api_key"] = "sk-test"
    config_path = tmp_path / "hebb.json"
    config_path.write_text(json.dumps(config))
    return config_path


def _seed_interrupted_manifest(tmp_path: Path) -> None:
    """Drop a manifest with a still-``running`` run, as a crash would leave."""
    logs_dir = tmp_path / "logs" / "consolidation"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "manifest.json").write_text(
        json.dumps(
            [
                {
                    "run_id": "deadbeef0001",
                    "trigger": "scheduled",
                    "status": "running",
                    "started_at": 1.0,
                    "finished_at": None,
                    "last_heartbeat": 1.0,
                    "processed": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "errors": [],
                    "log_file": "run-deadbeef0001.log",
                }
            ]
        )
    )


def _reset_tracker() -> None:
    from hebb.server import consolidation_tracker as tracker

    tracker._runs.clear()
    tracker._handlers.clear()
    tracker._logs_dir = None


def test_catchup_scheduled_after_interrupted_run_with_pending(tmp_path: Path) -> None:
    _reset_tracker()
    config_path = _write_config(tmp_path, with_llm=True)

    with (
        patch("hebb.config.loader.find_config_file", return_value=config_path),
        patch("hebb.embedding.factory.create_embedder", side_effect=_mock_create_embedder),
    ):
        from hebb.server.app import create_app

        # First boot: write a working memory into the HIPPOCAMPUS inbox, then
        # shut the server down cleanly.
        with TestClient(create_app()) as c:
            resp = c.post(
                "/api/v1/memories",
                json={"content": "a pending working memory", "partition_id": "mem_hippocampus"},
            )
            assert resp.status_code in (200, 201), resp.text

        # Simulate a crash mid-consolidation: a run left "running" in the manifest.
        _reset_tracker()
        _seed_interrupted_manifest(tmp_path)

        # Second boot: lifespan reaps the interrupted run and, with memories
        # still pending + an LLM configured, schedules the catch-up.
        with TestClient(create_app()) as c:
            app = c.app
            from hebb.server import consolidation_tracker as tracker

            recovered = tracker.get_run("deadbeef0001")
            assert recovered is not None
            assert recovered.status == "interrupted"

            job = app.state.scheduler.scheduler.get_job("consolidation_catchup")
            assert job is not None, "expected a catch-up job to resume the interrupted run"

    _reset_tracker()


def test_no_catchup_without_llm(tmp_path: Path) -> None:
    """No LLM configured → no catch-up scheduled (consolidation is a no-op)."""
    _reset_tracker()
    config_path = _write_config(tmp_path, with_llm=False)
    _seed_interrupted_manifest(tmp_path)

    with (
        patch("hebb.config.loader.find_config_file", return_value=config_path),
        patch("hebb.embedding.factory.create_embedder", side_effect=_mock_create_embedder),
    ):
        from hebb.server.app import create_app

        with TestClient(create_app()) as c:
            app = c.app
            assert app.state.scheduler.scheduler.get_job("consolidation_catchup") is None

    _reset_tracker()
