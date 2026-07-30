"""Local embedding provider using sentence-transformers."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from pathlib import Path
from typing import cast

from hebb.embedding.catalog import model_cache_dir, model_dir_complete, workspace_model_available

logger = logging.getLogger(__name__)


def _install_relative_models_dir(model_name: str) -> Path:
    """Install-relative ``<repo>/models/<id>`` fallback path.

    Used when the active workspace lacks a model dir — e.g. the eval
    harness sets ``HEBB_HOME=eval/workdirs/<bench>`` for db/kg isolation,
    but model weights legitimately live next to the source tree.
    """
    return Path(__file__).resolve().parent.parent.parent.parent / "models" / model_name


def _workspace_models_dir(model_name: str) -> Path:
    """Return the directory to load the model from.

    Prefer ``<workspace>/models/<id>`` (the per-workspace cache the
    embedding catalog populates) but fall back to the install-relative
    ``<repo>/models/<id>`` when the workspace path is missing the model.
    This lets eval runs (HEBB_HOME=workdir) reuse the project-root model
    cache without symlinks.
    """
    install_relative = _install_relative_models_dir(model_name)
    try:
        from hebb.config.workspace import resolve_workspace

        workspace = resolve_workspace()
        workspace_path = model_cache_dir(workspace, model_name)
        # Prefer a fully-downloaded copy; never let a half-downloaded workspace
        # dir shadow a complete install-relative one.
        if model_dir_complete(workspace_path):
            return workspace_path
        if model_dir_complete(install_relative):
            return install_relative
        # Neither is complete: fall back to the workspace dir if it exists (it is
        # also the download target), otherwise the install-relative path.
        return workspace_path if workspace_path.is_dir() else install_relative
    except Exception:
        return install_relative


def is_model_cached(model_name: str) -> bool:
    """Check if a sentence-transformers model is already cached locally."""
    try:
        from hebb.config.workspace import resolve_workspace

        if workspace_model_available(resolve_workspace(), model_name):
            return True
    except Exception:
        pass

    # Install-relative fallback — same as _workspace_models_dir uses.
    if model_dir_complete(_install_relative_models_dir(model_name)):
        return True

    try:
        from huggingface_hub import try_to_load_from_cache

        # A config alone is not enough — an interrupted download can cache the
        # config without the weights. Require a weight file to be cached too.
        if not isinstance(try_to_load_from_cache(model_name, "config.json"), (str, Path)):
            return False
        return any(
            isinstance(try_to_load_from_cache(model_name, weight), (str, Path))
            for weight in ("model.safetensors", "pytorch_model.bin")
        )
    except Exception:
        return False


def is_ml_stack_present() -> bool:
    """Return whether the local ML stack (sentence-transformers + torch) is importable.

    A lean install (``pip install hebb-mind`` without the ``local`` extra)
    omits this stack, and both :class:`LocalEmbedder` and the local reranker
    pull ``torch`` in transitively via ``sentence_transformers``. Checking the
    former alone would report "importable" for an install where ``torch`` was
    later removed — the embedder would then hard-fail with ``ModuleNotFoundError``
    at construction. The ``doctor`` and ``setup`` CLI commands share this single
    source of truth so their diagnostics can never disagree.

    Args:
        None.

    Returns:
        ``True`` iff both ``sentence_transformers`` and ``torch`` expose an
        importable module spec.

    Raises:
        Nothing — availability is probed with :func:`importlib.util.find_spec`,
        which returns ``None`` (never raises) when a module is absent.
    """
    import importlib.util

    return (
        importlib.util.find_spec("sentence_transformers") is not None
        and importlib.util.find_spec("torch") is not None
    )


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

        # Only load from the local dir when it actually has weights — an
        # interrupted download leaves config/tokenizer without the model
        # backbone. A partial dir must not shadow a complete copy in the HF
        # hub cache (the `cached` branch), or SentenceTransformer fails with
        # "no file named model.safetensors, or pytorch_model.bin …".
        if model_dir_complete(local_path):
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
        # mode at import time. The optional import AND the model load share one
        # try/finally so a missing-dependency ModuleNotFoundError also restores
        # the caller's HF_HUB_OFFLINE (no env-var leak on a lean install).
        try:
            try:
                from sentence_transformers import SentenceTransformer
            except ModuleNotFoundError as e:
                raise ModuleNotFoundError(
                    "Local embedding needs the ML stack (sentence-transformers + torch). "
                    "Run `hebb setup` to install it, or `pip install hebb-mind[local]`, "
                    "or switch to an API provider: `hebb config set embedding_provider api`.",
                    name=e.name,
                ) from e

            self._model = SentenceTransformer(load_target)
        finally:
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

    async def aclose(self) -> None:
        """Release provider resources. No-op — the model holds no network handles."""
        return None


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

    async def aclose(self) -> None:
        """Release provider resources. No-op — nothing is held."""
        return None
