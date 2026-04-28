"""Embedding provider factory — selects local or API embedder based on config."""

from __future__ import annotations

import logging

from hippocampus.config.settings import Settings
from hippocampus.embedding.base import EmbeddingProvider
from hippocampus.embedding.local import LocalEmbedder, NoopEmbedder

logger = logging.getLogger(__name__)

# Known model dimensions for auto-detection
KNOWN_DIMS: dict[str, int] = {
    # Local (sentence-transformers)
    "all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "all-mpnet-base-v2": 768,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "paraphrase-multilingual-mpnet-base-v2": 768,
    "BAAI/bge-m3": 1024,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
    "intfloat/multilingual-e5-small": 384,
    "intfloat/multilingual-e5-base": 768,
    "intfloat/multilingual-e5-large": 1024,
    # API (OpenAI)
    "openai/text-embedding-3-small": 1536,
    "openai/text-embedding-3-large": 3072,
    "openai/text-embedding-ada-002": 1536,
    # API (Cohere)
    "cohere/embed-english-v3.0": 1024,
    "cohere/embed-multilingual-v3.0": 1024,
    "cohere/embed-english-light-v3.0": 384,
    "cohere/embed-multilingual-light-v3.0": 384,
}


async def create_embedder(settings: Settings) -> EmbeddingProvider:
    """Create the appropriate embedding provider based on settings."""
    if not settings.embedding_enabled:
        logger.info("Embedding disabled by config")
        return NoopEmbedder(settings.embedding_dim)

    provider = settings.embedding_provider

    if provider == "api":
        return await _create_api_embedder(settings)
    else:
        return _create_local_embedder(settings)


def _create_local_embedder(settings: Settings) -> EmbeddingProvider:
    """Create a local sentence-transformers embedder."""
    try:
        logger.info("Loading local embedding model: %s", settings.embedding_model)
        embedder = LocalEmbedder(settings.embedding_model, hf_endpoint=settings.hf_endpoint)
        return embedder
    except Exception:
        logger.warning("Failed to load local embedding model, vector search disabled", exc_info=True)
        return NoopEmbedder(settings.embedding_dim)


async def _create_api_embedder(settings: Settings) -> EmbeddingProvider:
    """Create a cloud API embedder via litellm."""
    from hippocampus.embedding.api import ApiEmbedder

    model = settings.embedding_model
    api_key = settings.embedding_api_key  # no fallback — embedding and LLM may use different providers
    base_url = settings.embedding_base_url

    if not base_url:
        logger.warning("embedding_base_url is required for API embedding provider, vector search disabled")
        return NoopEmbedder(settings.embedding_dim)

    # Detect dimension
    dim = await _detect_api_dimension(model, api_key, base_url, settings.embedding_dim)

    return ApiEmbedder(model=model, api_key=api_key, base_url=base_url, dimension=dim)


async def _detect_api_dimension(model: str, api_key: str | None, base_url: str | None, fallback_dim: int) -> int:
    """Detect embedding dimension: known table → probe API → fallback."""
    # 1. Check known models table
    if model in KNOWN_DIMS:
        dim = KNOWN_DIMS[model]
        logger.info("Embedding dimension from known models: %s → %d", model, dim)
        return dim

    # 2. Probe with a test request
    try:
        from litellm import aembedding

        logger.info("Probing embedding dimension for model: %s", model)
        kwargs: dict = {"model": model, "input": ["dimension probe"]}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["api_base"] = base_url
        response = await aembedding(**kwargs)
        dim = len(response.data[0]["embedding"])
        logger.info("Detected embedding dimension via probe: %d", dim)
        return dim
    except Exception:
        logger.warning(
            "Could not detect embedding dimension for %s, using fallback=%d", model, fallback_dim, exc_info=True
        )
        return fallback_dim
