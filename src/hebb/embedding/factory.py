"""Embedding provider factory — selects local or API embedder based on config."""

from __future__ import annotations

import logging
from typing import Any

from hebb.config.settings import Settings
from hebb.embedding.base import EmbeddingProvider
from hebb.embedding.local import LocalEmbedder, NoopEmbedder

logger = logging.getLogger(__name__)

# Known model dimensions for auto-detection
KNOWN_DIMS: dict[str, int] = {
    # Local (sentence-transformers)
    "all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "all-mpnet-base-v2": 768,
    "sentence-transformers/all-mpnet-base-v2": 768,
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
    except ModuleNotFoundError as e:
        # The local ML stack (sentence-transformers + torch, including transitive
        # deps like tokenizers/huggingface_hub/safetensors) is not installed.
        # Degrade loudly with an actionable hint AND name the actually-missing
        # module so a transitive culprit isn't hidden behind a static message.
        logger.warning(
            "Local embedding stack not installed (missing %s). "
            "Vector search disabled. Install it with `pip install hebb-mind[local]` "
            "or `hebb setup`, or switch to an API provider "
            "(`hebb config set embedding_provider api`).",
            e.name or "a local-stack module",
        )
        return NoopEmbedder(settings.embedding_dim)
    except Exception:
        logger.warning("Failed to load local embedding model, vector search disabled", exc_info=True)
        return NoopEmbedder(settings.embedding_dim)


async def _create_api_embedder(settings: Settings) -> EmbeddingProvider:
    """Create a cloud API embedder — litellm or a user-defined HTTP request."""
    if settings.embedding_api_mode == "custom":
        return await _create_custom_http_embedder(settings)

    from hebb.embedding.api import ApiEmbedder

    model = settings.embedding_model
    api_key = settings.embedding_api_key  # no fallback — embedding and LLM may use different providers
    base_url = settings.embedding_base_url

    if not base_url:
        logger.warning("embedding_base_url is required for API embedding provider, vector search disabled")
        return NoopEmbedder(settings.embedding_dim)

    # Detect dimension. A None result means the model is unknown *and* the
    # probe failed even after a retry — we must NOT guess a dimension, because
    # a wrong vec0 width silently breaks every real write. Disable vector
    # search instead (NoopEmbedder) so the failure is loud and recoverable.
    dim = await _detect_api_dimension(model, api_key, base_url)
    if dim is None:
        logger.warning(
            "Could not determine embedding dimension for %s after retry; vector search disabled "
            "(refusing to guess a dimension)",
            model,
        )
        return NoopEmbedder(settings.embedding_dim)

    return ApiEmbedder(model=model, api_key=api_key, base_url=base_url, dimension=dim)


async def _create_custom_http_embedder(settings: Settings) -> EmbeddingProvider:
    """Create an embedder driven by a fully user-defined HTTP request."""
    from hebb.embedding.http_custom import CustomHttpEmbedder, parse_headers

    url = settings.embedding_http_url
    body = settings.embedding_http_body
    if not url or not body:
        logger.warning(
            "embedding_http_url and embedding_http_body are required for custom HTTP embedding, vector search disabled"
        )
        return NoopEmbedder(settings.embedding_dim)

    try:
        headers = parse_headers(settings.embedding_http_headers)
        embedder = CustomHttpEmbedder(
            method=settings.embedding_http_method or "POST",
            url=url,
            headers=headers,
            body_template=body,
            response_path=settings.embedding_http_response_path or "data.*.embedding",
            dimension=settings.embedding_dim,
        )
    except ValueError:
        logger.warning("Invalid custom HTTP embedding configuration, vector search disabled", exc_info=True)
        return NoopEmbedder(settings.embedding_dim)

    # Probe the endpoint to detect the embedding dimension, retrying once on
    # transient failure. On persistent failure we MUST NOT keep the guessed
    # settings.embedding_dim — a wrong vec0 width silently breaks every write —
    # so we close the throwaway client and disable vector search instead.
    attempts = 2
    for attempt in range(1, attempts + 1):
        try:
            vec = await embedder.embed("dimension probe")
            embedder.set_dimension(len(vec))
            logger.info("Custom HTTP embedding dimension detected via probe: %d", len(vec))
            return embedder
        except Exception:
            if attempt < attempts:
                logger.warning("Custom HTTP embedding dimension probe failed, retrying", exc_info=True)
            else:
                logger.warning(
                    "Could not probe custom HTTP embedding dimension after %d attempts; vector search disabled "
                    "(refusing to guess a dimension)",
                    attempts,
                )
    # Probe failed: release the throwaway client and disable vector search.
    await embedder.aclose()
    return NoopEmbedder(settings.embedding_dim)


async def _detect_api_dimension(model: str, api_key: str | None, base_url: str | None) -> int | None:
    """Detect embedding dimension: known table → probe API (one retry).

    Args:
        model: The embedding model identifier.
        api_key: Optional API key passed through to litellm.
        base_url: Optional API base URL passed through to litellm.

    Returns:
        The detected dimension, or ``None`` when the model is unknown and the
        probe fails even after one retry. Callers MUST treat ``None`` as
        "disable vector search" rather than guessing a width — a mismatched
        vec0 dimension silently breaks every subsequent write.
    """
    # 1. Check known models table
    if model in KNOWN_DIMS:
        dim = KNOWN_DIMS[model]
        logger.info("Embedding dimension from known models: %s → %d", model, dim)
        return dim

    # 2. Probe with a test request, retrying once on transient failure.
    from litellm import aembedding

    kwargs: dict[str, Any] = {"model": model, "input": ["dimension probe"]}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    attempts = 2
    for attempt in range(1, attempts + 1):
        try:
            logger.info("Probing embedding dimension for model: %s (attempt %d/%d)", model, attempt, attempts)
            response = await aembedding(**kwargs)
            dim = len(response.data[0]["embedding"])
            logger.info("Detected embedding dimension via probe: %d", dim)
            return dim
        except Exception:
            if attempt < attempts:
                logger.warning("Embedding dimension probe for %s failed, retrying", model, exc_info=True)
            else:
                logger.warning("Could not detect embedding dimension for %s after %d attempts", model, attempts)
    return None
