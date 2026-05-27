"""Reranker factory — selects local provider, ``None`` when disabled."""

from __future__ import annotations

import logging

from hebb.config.settings import Settings
from hebb.retrieval.rerank.base import Reranker
from hebb.retrieval.rerank.local import LocalReranker

logger = logging.getLogger(__name__)


def create_reranker(settings: Settings) -> Reranker | None:
    """Build a reranker per settings; return ``None`` when disabled.

    Returning ``None`` (not a no-op) lets the searcher skip the entire
    rerank phase with a single ``is None`` check — keeping the
    rerank-off fast path indistinguishable from the pre-rerank code.
    """
    if not settings.rerank_enabled:
        return None

    provider = settings.rerank_provider
    if provider != "local":
        logger.warning(
            "Unsupported rerank_provider=%r (only 'local' is implemented); rerank disabled",
            provider,
        )
        return None

    try:
        return LocalReranker(
            model_name=settings.rerank_model,
            top_n=settings.rerank_top_n,
            hf_endpoint=settings.hf_endpoint,
        )
    except Exception:
        logger.warning(
            "Failed to load reranker %r, rerank disabled",
            settings.rerank_model,
            exc_info=True,
        )
        return None
