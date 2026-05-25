"""Local embedding provider using sentence-transformers."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from pathlib import Path
from typing import cast

from hebb.embedding.catalog import model_cache_dir, workspace_model_available

logger = logging.getLogger(__name__)


def _workspace_models_dir(model_name: str) -> Path:
    """Return the models/ directory within the current workspace.

    Falls back to the install-relative path if no workspace is found.
    """
    try:
        from hebb.config.workspace import resolve_workspace

        workspace = resolve_workspace()
        return model_cache_dir(workspace, model_name)
    except Exception:
        # Fallback: install-relative path (legacy behavior)
        return Path(__file__).resolve().parent.parent.parent.parent / "models" / model_name


def is_model_cached(model_name: str) -> bool:
    """Check if a sentence-transformers model is already cached locally."""
    try:
        from hebb.config.workspace import resolve_workspace

        if workspace_model_available(resolve_workspace(), model_name):
            return True

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

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", hf_endpoint: str | None = None) -> None:
        import os

        # Set HuggingFace mirror endpoint if configured
        if hf_endpoint:
            os.environ["HF_ENDPOINT"] = hf_endpoint
            logger.info("Using HuggingFace mirror: %s", hf_endpoint)

        # Prefer local model from workspace models/ directory, then install-relative
        local_path = _workspace_models_dir(model_name)

        # Check cache in offline mode to avoid network hangs.
        # Must set env var BEFORE importing sentence_transformers/huggingface_hub
        # because the library reads HF_HUB_OFFLINE at import time.
        old_offline = os.environ.get("HF_HUB_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "1"
        cached = is_model_cached(model_name)

        if local_path.is_dir():
            logger.info("Loading local embedding model: %s", local_path)
            load_target = str(local_path)
            use_offline = True
        elif cached:
            logger.info("Loading cached embedding model: %s", model_name)
            load_target = model_name
            use_offline = True
        else:
            logger.info("Downloading embedding model: %s (first time, may take a while)", model_name)
            load_target = model_name
            use_offline = False

        # Restore original offline setting if we need to download
        if not use_offline:
            if old_offline is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = old_offline

        # Import after env var is set — huggingface_hub caches offline
        # mode at import time.
        from sentence_transformers import SentenceTransformer

        try:
            self._model = SentenceTransformer(load_target)
        finally:
            # Restore env for non-offline case is already done above;
            # for offline case, restore now.
            if use_offline:
                if old_offline is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = old_offline

        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info("Embedding model ready: %s (dim=%d)", model_name, self._dimension)

    @property
    def dimension(self) -> int:
        return int(self._dimension)

    async def embed(self, text: str) -> list[float]:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, partial(self._model.encode, text, normalize_embeddings=True))
        return cast("list[float]", result.tolist())

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, partial(self._model.encode, texts, normalize_embeddings=True))
        return cast("list[list[float]]", results.tolist())


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
