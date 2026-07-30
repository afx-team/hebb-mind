"""Tests for the embedding/rerank factory missing-stack diagnostics (Copilot #2/#3).

When the local ML stack is incomplete, ``_create_local_embedder`` /
``create_reranker`` must surface the *actually-missing* module (``e.name``),
not a static "install the local stack" hint that hides whether the culprit is
``sentence_transformers``, ``torch``, or a transitive dep like ``tokenizers`` /
``huggingface_hub`` / ``safetensors``.
"""

from __future__ import annotations

import pytest

from hebb.config.settings import Settings
from hebb.embedding import factory as embed_factory
from hebb.embedding.local import NoopEmbedder
from hebb.retrieval.rerank import factory as rerank_factory


async def test_local_embedder_fallback_names_missing_module(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _missing_tokenizers(*args: object, **kwargs: object) -> None:
        raise ModuleNotFoundError("No module named 'tokenizers'", name="tokenizers")

    monkeypatch.setattr(embed_factory, "LocalEmbedder", _missing_tokenizers)

    settings = Settings(
        embedding_enabled=True,
        embedding_provider="local",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        embedding_dim=384,
    )
    with caplog.at_level("WARNING"):
        emb = await embed_factory.create_embedder(settings)

    assert isinstance(emb, NoopEmbedder)
    # The transitive culprit is named, not hidden behind a static message.
    assert "tokenizers" in caplog.text
    # The actionable install hint is still emitted.
    assert "hebb-mind[local]" in caplog.text


def test_local_reranker_fallback_names_missing_module(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _missing_safetensors(*args: object, **kwargs: object) -> None:
        raise ModuleNotFoundError("No module named 'safetensors'", name="safetensors")

    monkeypatch.setattr(rerank_factory, "LocalReranker", _missing_safetensors)

    settings = Settings(
        rerank_enabled=True,
        rerank_provider="local",
        rerank_model="BAAI/bge-reranker-base",
        rerank_top_n=30,
    )
    with caplog.at_level("WARNING"):
        result = rerank_factory.create_reranker(settings)

    assert result is None
    assert "safetensors" in caplog.text
    assert "hebb-mind[local]" in caplog.text
