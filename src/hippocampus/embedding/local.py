"""Local embedding provider using sentence-transformers."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from pathlib import Path

logger = logging.getLogger(__name__)

# Bundled model directory: {project_root}/models/
_MODELS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"


def _resolve_model_path(model_name: str) -> str:
    """Resolve model name to a local path if bundled, otherwise return as-is for HF download."""
    local_path = _MODELS_DIR / model_name
    if local_path.is_dir() and (local_path / "config.json").exists():
        logger.info("Loading bundled model from %s", local_path)
        return str(local_path)
    logger.info("Model not bundled locally, loading from HuggingFace: %s", model_name)
    return model_name


class LocalEmbedder:
    """Embedding provider using a local sentence-transformers model."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        import os

        from sentence_transformers import SentenceTransformer

        model_path = _resolve_model_path(model_name)

        # Suppress safetensors LOAD REPORT (writes directly to OS-level file descriptors)
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stdout_fd = os.dup(1)
        old_stderr_fd = os.dup(2)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        try:
            self._model = SentenceTransformer(
                model_path, local_files_only=(model_path != model_name)
            )
        finally:
            os.dup2(old_stdout_fd, 1)
            os.dup2(old_stderr_fd, 2)
            os.close(old_stdout_fd)
            os.close(old_stderr_fd)
            os.close(devnull)

        self._dimension = self._model.get_embedding_dimension()
        logger.info("Embedding model loaded: dim=%d", self._dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, partial(self._model.encode, text, normalize_embeddings=True)
        )
        return result.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, partial(self._model.encode, texts, normalize_embeddings=True)
        )
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
