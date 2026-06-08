"""Abstract embedding provider protocol."""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Interface for text embedding generation."""

    @property
    def dimension(self) -> int: ...

    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    async def aclose(self) -> None:
        """Release any provider-held resources (HTTP clients, pools, etc.).

        Implementations that hold no resources may treat this as a no-op.
        Callers should guard the call with ``hasattr`` since older third-party
        embedders may predate this method.
        """
        ...
