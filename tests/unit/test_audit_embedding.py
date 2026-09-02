"""Embedding-surface audit tests (Lane G-embedding).

Guards the embedding correctness / lifecycle / dimension-safety class of
defects:

- F4: every provider (not just the local one) must return unit-norm vectors,
  because the vector store's cosine conversion ``cosine = 1 - d²/2`` only holds
  for unit vectors.
- F5: embedders expose an ``aclose()`` that releases held resources (the custom
  HTTP client in particular).
- F8: a failed startup dimension probe must disable vector search
  (``NoopEmbedder``) rather than guess a wrong width.
- F1: the library facade must size the vec0 store from the embedder's true
  dimension, i.e. create the embedder before the stores.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from hebb.config.settings import Settings
from hebb.embedding import factory
from hebb.embedding.http_custom import CustomHttpEmbedder
from hebb.embedding.local import NoopEmbedder


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def _stub_request(embedder: CustomHttpEmbedder, response: Any) -> None:
    """Replace the network call with a canned response (or a callable)."""

    async def _fake(payload: Any) -> Any:
        return response(payload) if callable(response) else response

    embedder._request = _fake  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# F4 — unit-norm vectors from every provider
# ---------------------------------------------------------------------------


class TestApiEmbedderNormalizes:
    async def test_embed_returns_unit_vector(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hebb.embedding import api as api_mod

        async def fake_aembedding(**kwargs: Any) -> Any:
            return type("R", (), {"data": [{"embedding": [3.0, 4.0], "index": 0}]})()

        monkeypatch.setattr(api_mod, "aembedding", fake_aembedding)
        emb = api_mod.ApiEmbedder(model="m", dimension=2)
        vec = await emb.embed("hi")
        assert _norm(vec) == pytest.approx(1.0)
        # 3-4-5 triangle → unit vector is (0.6, 0.8)
        assert vec == pytest.approx([0.6, 0.8])

    async def test_embed_batch_returns_unit_vectors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hebb.embedding import api as api_mod

        async def fake_aembedding(**kwargs: Any) -> Any:
            data = [
                {"embedding": [3.0, 4.0], "index": 0},
                {"embedding": [0.0, 5.0], "index": 1},
            ]
            return type("R", (), {"data": data})()

        monkeypatch.setattr(api_mod, "aembedding", fake_aembedding)
        emb = api_mod.ApiEmbedder(model="m", dimension=2)
        out = await emb.embed_batch(["a", "b"])
        assert all(_norm(v) == pytest.approx(1.0) for v in out)
        assert out[0] == pytest.approx([0.6, 0.8])
        assert out[1] == pytest.approx([0.0, 1.0])


class TestCustomHttpEmbedderNormalizes:
    async def test_batch_mode_unit_vectors(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
            response_path="data.*.embedding",
        )
        _stub_request(emb, {"data": [{"embedding": [3.0, 4.0]}, {"embedding": [0.0, 2.0]}]})
        out = await emb.embed_batch(["a", "b"])
        assert all(_norm(v) == pytest.approx(1.0) for v in out)
        assert out[0] == pytest.approx([0.6, 0.8])
        assert out[1] == pytest.approx([0.0, 1.0])

    async def test_per_text_mode_unit_vectors(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"text": {{text}}}',
            response_path="embedding",
        )
        _stub_request(emb, lambda payload: {"embedding": [6.0, 8.0]})
        out = await emb.embed_batch(["a"])
        assert _norm(out[0]) == pytest.approx(1.0)
        assert out[0] == pytest.approx([0.6, 0.8])

    async def test_zero_vector_is_safe(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
        )
        _stub_request(emb, {"data": [{"embedding": [0.0, 0.0]}]})
        out = await emb.embed_batch(["a"])
        # A zero vector has no direction; it must be returned unchanged, not NaN.
        assert out[0] == [0.0, 0.0]


# ---------------------------------------------------------------------------
# F5 — aclose() releases the HTTP client
# ---------------------------------------------------------------------------


class TestAclose:
    async def test_custom_http_aclose_closes_client(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
        )
        # Force a client to exist, then close it.
        client = emb._get_client()
        assert client is not None
        assert emb._client is not None
        await emb.aclose()
        assert emb._client is None
        assert client.is_closed

    async def test_custom_http_aclose_idempotent(self) -> None:
        emb = CustomHttpEmbedder(
            method="POST",
            url="https://x/embed",
            headers={},
            body_template='{"input": {{input}}}',
        )
        # No client opened yet — aclose must be a no-op, callable twice.
        await emb.aclose()
        await emb.aclose()
        assert emb._client is None

    async def test_api_embedder_aclose_is_noop(self) -> None:
        from hebb.embedding.api import ApiEmbedder

        emb = ApiEmbedder(model="m", dimension=8)
        # Must not raise; litellm manages its own clients.
        await emb.aclose()


# ---------------------------------------------------------------------------
# F8 — probe failure disables vector search instead of guessing a dimension
# ---------------------------------------------------------------------------


class TestProbeFailureFallsBackToNoop:
    async def test_api_probe_failure_returns_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Unknown model (not in KNOWN_DIMS) whose probe always fails.
        async def failing_detect(model: str, api_key: Any, base_url: Any) -> int | None:
            return None

        monkeypatch.setattr(factory, "_detect_api_dimension", failing_detect)
        settings = Settings(
            embedding_enabled=True,
            embedding_provider="api",
            embedding_api_mode="litellm",
            embedding_model="some/unknown-model",
            embedding_base_url="https://api.example.com",
            embedding_dim=384,
        )
        emb = await factory.create_embedder(settings)
        assert isinstance(emb, NoopEmbedder)

    async def test_detect_dimension_retries_then_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"n": 0}

        async def always_fail(**kwargs: Any) -> Any:
            calls["n"] += 1
            raise RuntimeError("endpoint down")

        import litellm

        monkeypatch.setattr(litellm, "aembedding", always_fail)
        dim = await factory._detect_api_dimension("some/unknown-model", None, "https://api.example.com")
        assert dim is None
        # One initial attempt + one retry.
        assert calls["n"] == 2

    async def test_detect_dimension_known_model_skips_probe(self) -> None:
        # Known model resolves from the table without any network probe.
        dim = await factory._detect_api_dimension("openai/text-embedding-3-small", None, "https://x")
        assert dim == 1536

    async def test_custom_http_probe_failure_returns_noop_and_closes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        closed: list[bool] = []

        from hebb.embedding import http_custom as hc_mod

        class FailingProbeEmbedder(CustomHttpEmbedder):
            async def embed(self, text: str) -> list[float]:
                raise RuntimeError("endpoint down")

            async def aclose(self) -> None:
                closed.append(True)
                await super().aclose()

        monkeypatch.setattr(hc_mod, "CustomHttpEmbedder", FailingProbeEmbedder)
        # factory imports the symbol inside the function, so patch the module it
        # imports from.
        settings = Settings(
            embedding_enabled=True,
            embedding_provider="api",
            embedding_api_mode="custom",
            embedding_http_url="https://api.example.com/embed",
            embedding_http_body='{"input": {{input}}}',
            embedding_dim=384,
        )
        emb = await factory.create_embedder(settings)
        assert isinstance(emb, NoopEmbedder)
        # The throwaway probe client must have been closed.
        assert closed == [True]


# ---------------------------------------------------------------------------
# F1 — library facade sizes vec0 from the embedder's true dimension
# ---------------------------------------------------------------------------


class TestLibrarySizesVecFromEmbedderDim:
    def test_async_start_creates_embedder_before_stores(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """The embedder dim must be pinned onto settings BEFORE create_stores.

        We stub create_embedder to report a width that differs from the
        configured embedding_dim and assert create_stores observes the corrected
        value (proving the ordering / F1 fix).
        """
        import hebb.api as api_mod

        observed: dict[str, int] = {}

        class FakeEmbedder:
            dimension = 1024

            async def embed(self, text: str) -> list[float]:
                return [0.0] * 1024

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return [[0.0] * 1024 for _ in texts]

            async def aclose(self) -> None:
                return None

        async def fake_create_embedder(settings: Settings) -> Any:
            return FakeEmbedder()

        class FakePartitionStore:
            async def ensure_defaults(self) -> None:
                return None

        class FakeCtx:
            memory_store = object()
            partition_store = FakePartitionStore()
            write_lock = None  # SQLite backend would pass a shared lock (Issue #36)

            async def close(self) -> None:
                return None

        async def fake_create_stores(settings: Settings) -> Any:
            # Capture the dim the storage layer would size vec0 from.
            observed["dim"] = settings.embedding_dim
            return FakeCtx()

        class FakeKG:
            def __init__(self, path: Any, lock: Any = None) -> None:
                pass

            def save(self) -> None:
                return None

        class FakeSearcher:
            def __init__(self, **kwargs: Any) -> None:
                pass

        monkeypatch.setattr("hebb.embedding.factory.create_embedder", fake_create_embedder)
        monkeypatch.setattr("hebb.storage.factory.create_stores", fake_create_stores)
        monkeypatch.setattr("hebb.graph.knowledge_graph.KnowledgeGraph", FakeKG)
        monkeypatch.setattr("hebb.retrieval.searcher.MemorySearcher", FakeSearcher)

        settings = Settings(
            embedding_enabled=True,
            embedding_dim=384,  # deliberately wrong vs the model's true 1024
            home_dir=tmp_path,  # kg_path/db_path derive from this
        )
        hc = api_mod.HebbMind(config=settings, autostart=False)
        hc._ensure_started()
        try:
            assert observed["dim"] == 1024, "create_stores must see the embedder's true dimension"
            assert settings.embedding_dim == 1024
        finally:
            hc.close()
