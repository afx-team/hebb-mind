"""Local embedding provider using sentence-transformers."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from pathlib import Path

logger = logging.getLogger(__name__)


def is_model_cached(model_name: str) -> bool:
    """Check if a sentence-transformers model is already cached locally."""
    try:
        from huggingface_hub import try_to_load_from_cache

        # sentence-transformers models always have config.json
        result = try_to_load_from_cache(model_name, "config.json")
        return result is not None and isinstance(result, (str, Path))
    except Exception:
        return False


class LocalEmbedder:
    """Embedding provider using a local sentence-transformers model.

    Models are downloaded from HuggingFace Hub on first use and cached
    in ~/.cache/huggingface/.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        import os

        from sentence_transformers import SentenceTransformer

        # Prefer local model from project models/ directory
        local_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / model_name
        if local_path.is_dir():
            logger.info("Loading local embedding model: %s", local_path)
            load_target = str(local_path)
        elif is_model_cached(model_name):
            logger.info("Loading cached embedding model: %s", model_name)
            load_target = model_name
        else:
            logger.info("Downloading embedding model: %s (first time, may take a while)", model_name)
            load_target = model_name

        # Suppress stdout/stderr for local/cached loads
        if local_path.is_dir() or is_model_cached(model_name):
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_stdout_fd = os.dup(1)
            old_stderr_fd = os.dup(2)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            try:
                self._model = SentenceTransformer(load_target)
            finally:
                os.dup2(old_stdout_fd, 1)
                os.dup2(old_stderr_fd, 2)
                os.close(old_stdout_fd)
                os.close(old_stderr_fd)
                os.close(devnull)
        else:
            self._model = SentenceTransformer(load_target)

        self._dimension = self._model.get_embedding_dimension()
        logger.info("Embedding model ready: %s (dim=%d)", model_name, self._dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, partial(self._model.encode, text, normalize_embeddings=True))
        return result.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, partial(self._model.encode, texts, normalize_embeddings=True))
        return results.tolist()


class NoopEmbedder:
    """Fallback embedder when no model is available. Vector search will be disabled."""

    def __init__(self, dimension: int = 384) -> None:
        self._dimension = dimension
        logger.warning("Using NoopEmbedder — vector search is disabled")

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]
