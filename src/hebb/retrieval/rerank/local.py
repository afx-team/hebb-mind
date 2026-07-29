"""Local cross-encoder reranker via sentence-transformers."""

from __future__ import annotations

import asyncio
import logging
import os
from functools import partial
from typing import cast

logger = logging.getLogger(__name__)


def _is_cross_encoder_cached(model_name: str) -> bool:
    """Best-effort check whether a CrossEncoder model is on disk already."""
    try:
        from huggingface_hub import try_to_load_from_cache

        result = try_to_load_from_cache(model_name, "config.json")
        return result is not None and isinstance(result, (str, os.PathLike))
    except Exception:
        return False


class LocalReranker:
    """Cross-encoder reranker (sentence-transformers ``CrossEncoder``).

    Lazy-loads the model on construction the same way ``LocalEmbedder``
    does: prefer cached weights, drop the offline flag only if we
    actually need to download.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        top_n: int = 30,
        hf_endpoint: str | None = None,
    ) -> None:
        if hf_endpoint:
            os.environ["HF_ENDPOINT"] = hf_endpoint
            logger.info("Reranker using HuggingFace mirror: %s", hf_endpoint)

        old_offline = os.environ.get("HF_HUB_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "1"
        cached = _is_cross_encoder_cached(model_name)

        if cached:
            logger.info("Loading cached reranker model: %s", model_name)
        else:
            logger.info("Downloading reranker model: %s (first time, may take a while)", model_name)
            # Force the offline flag off for the actual load — even if the
            # caller's env had HF_HUB_OFFLINE=1 (e.g. the eval harness sets
            # it on the server subprocess for reproducibility). Without
            # this, an uncached model in offline-by-default env never
            # downloads and CrossEncoder raises.
            os.environ.pop("HF_HUB_OFFLINE", None)

        try:
            from sentence_transformers import CrossEncoder
            from torch.nn import Sigmoid
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                "Local reranker needs the ML stack (sentence-transformers + torch). "
                "Run `hebb setup` to install it, or `pip install hebb-mind[local]`, "
                "or disable rerank: `hebb config set rerank_enabled false`."
            ) from e

        try:
            # No explicit max_length: CrossEncoder truncates long (query,
            # content) pairs to the tokenizer's model_max_length, which is the
            # model's own context window (512 for bge-reranker-base). Setting it
            # by hand only risks exceeding the model's position-embedding cap.
            self._model = CrossEncoder(model_name)
        finally:
            # Always restore the caller's original offline setting,
            # regardless of which path we took above.
            if old_offline is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = old_offline

        # Cross-encoders emit raw logits on an arbitrary scale. Apply sigmoid
        # so scores land in [0, 1] — consistent with the no-rerank composite,
        # so a single min_score / threshold scale works in both modes. Sigmoid
        # is monotonic, so the rerank ordering is unchanged.
        self._activation = Sigmoid()
        self._model_name = model_name
        self._top_n = top_n
        logger.info("Reranker ready: %s (top_n=%d, max_length=%s)", model_name, top_n, self._model.max_length)

    @property
    def top_n(self) -> int:
        return self._top_n

    async def score(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        pairs = [[query, c] for c in candidates]
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(self._model.predict, pairs, activation_fn=self._activation, convert_to_numpy=True),
        )
        return cast("list[float]", result.tolist())
