"""Cloud embedding provider via litellm."""

from __future__ import annotations

import logging
import math
from typing import Any, cast

from litellm import aembedding

logger = logging.getLogger(__name__)


def _l2_normalize(vector: list[float]) -> list[float]:
    """Return ``vector`` scaled to unit L2 norm.

    The vector-store cosine conversion (``cosine = 1 - d²/2``) only holds for
    unit vectors, so every provider must return normalized embeddings. A
    zero (or empty) vector is returned unchanged to avoid division by zero.

    Args:
        vector: The raw embedding to normalize.

    Returns:
        The unit-norm embedding, or the input unchanged if its norm is zero.
    """
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


class ApiEmbedder:
    """Embedding provider using cloud APIs (OpenAI, Cohere, DashScope, etc.) via litellm."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        dimension: int = 1536,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._dimension = dimension
        logger.info("ApiEmbedder initialized: model=%s, dim=%d", model, dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        kwargs: dict[str, Any] = {"model": self.model, "input": [text]}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url
        response = await aembedding(**kwargs)
        return _l2_normalize(cast("list[float]", response.data[0]["embedding"]))

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        kwargs: dict[str, Any] = {"model": self.model, "input": texts}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url
        response = await aembedding(**kwargs)
        # Sort by index to ensure order matches input
        sorted_data = sorted(response.data, key=lambda d: d["index"])
        return [_l2_normalize(d["embedding"]) for d in sorted_data]

    async def aclose(self) -> None:
        """Release provider resources. No-op — litellm manages its own clients."""
        return None
