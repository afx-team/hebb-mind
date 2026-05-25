"""Synchronous public facade over the (mostly async) Hebb Mind internals.

This module gives library users a one-liner entry point::

    from hebb import HebbMind

    hc = HebbMind()                     # default config / sqlite / local embed
    hc.add("user prefers dark mode", partition="mem_preference")
    for r in hc.search("dark mode preference", top_k=5):
        print(r.score, r.memory.content)
    hc.close()

The facade wires the same components that
:func:`hebb.server.app.create_app` builds for the FastAPI server —
storage, embedding, knowledge graph, searcher, and (optionally) the
consolidation pipeline — but exposes them as plain synchronous methods.

Internals stay async; the facade owns a private event loop running in a
dedicated background thread so that every sync call dispatches to it
with :func:`asyncio.run_coroutine_threadsafe`. This keeps the facade
usable from inside an outer event loop (e.g. Jupyter, FastAPI handlers)
without the ``RuntimeError: This event loop is already running``
complaint that a naive :func:`asyncio.run` wrapper would produce.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Coroutine
from concurrent.futures import Future
from pathlib import Path
from types import TracebackType
from typing import Any, TypeVar

from hebb.config.loader import load_settings
from hebb.config.settings import Settings
from hebb.constants import DEFAULT_PARTITION
from hebb.embedding.base import EmbeddingProvider
from hebb.exceptions import (
    ConfigError,
    EmbeddingError,
    HebbMindError,
    LLMError,
    MemoryNotFoundError,
    StorageError,
)
from hebb.graph.knowledge_graph import KnowledgeGraph
from hebb.models.memory import (
    Memory,
    MemoryCreate,
    MemoryMetadata,
    MemoryQuery,
    MemorySearchResult,
)
from hebb.retrieval.searcher import MemorySearcher
from hebb.storage.base import MemoryStore, PartitionStore

logger = logging.getLogger(__name__)

T = TypeVar("T")

# See `hebb.storage.base` — alias the builtin so class-scope annotations
# don't resolve to the `list` method defined on HebbMind below.
_List = list


class HebbMind:
    """Synchronous, batteries-included facade for the Hebb Mind memory framework.

    A single instance owns its own event loop, storage backend, embedder,
    knowledge graph, and searcher — equivalent to what the FastAPI server
    spins up at startup, minus the HTTP layer and (by default) the
    background scheduler.

    Args:
        config: Pre-built :class:`~hebb.config.settings.Settings`
            instance. Mutually exclusive with ``config_path``.
        config_path: Path to a ``hebb.json`` file. If neither
            ``config`` nor ``config_path`` is provided, the standard
            workspace lookup is used (cwd → ``$HEBB_HOME`` →
            ``~/.hebb``).
        autostart: If ``True`` (default), eagerly initialize storage,
            embedder, graph, and searcher inside ``__init__``. Set to
            ``False`` to defer the cost until the first call.

    Attributes:
        settings: The :class:`Settings` instance in use.

    Raises:
        ConfigError: If ``config`` and ``config_path`` are both set, or
            if config loading fails.
        StorageError: If the storage backend cannot be initialized
            (only raised lazily on the first operation when
            ``autostart=False``).
        EmbeddingError: If the embedding provider cannot be initialized.

    Example:
        >>> with HebbMind() as hc:
        ...     hc.add("I prefer dark mode", partition="mem_preference")
        ...     results = hc.search("appearance preferences")
        ...     for r in results:
        ...         print(r.score, r.memory.content)
    """

    def __init__(
        self,
        config: Settings | None = None,
        config_path: str | Path | None = None,
        *,
        autostart: bool = True,
    ) -> None:
        if config is not None and config_path is not None:
            raise ConfigError("Pass either 'config' or 'config_path', not both.")

        try:
            if config is not None:
                self.settings: Settings = config
            else:
                path = Path(config_path).expanduser() if config_path is not None else None
                self.settings = load_settings(path)
        except HebbMindError:
            raise
        except Exception as exc:  # noqa: BLE001 — translating to public type
            raise ConfigError(f"Failed to load Hebb Mind settings: {exc}") from exc

        # Background event loop (started lazily, owned by this instance).
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_ready = threading.Event()
        self._closed = False

        # Backend handles, populated by _ensure_started().
        self._memory_store: MemoryStore = None  # type: ignore[assignment]
        self._partition_store: PartitionStore = None  # type: ignore[assignment]
        self._embedder: EmbeddingProvider | None = None
        self._knowledge_graph: KnowledgeGraph | None = None
        self._searcher: MemorySearcher = None  # type: ignore[assignment]
        self._storage_close: Any = None
        self._started = False
        self._start_lock = threading.Lock()

        if autostart:
            self._ensure_started()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _start_loop(self) -> None:
        """Spin up the dedicated background event loop."""
        if self._loop_thread is not None:
            return

        def _run() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            self._loop_ready.set()
            try:
                loop.run_forever()
            finally:
                loop.close()

        self._loop_thread = threading.Thread(target=_run, name="hebb-loop", daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait()

    def _run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Schedule a coroutine on the background loop and block for the result."""
        if self._closed:
            raise HebbMindError("Hebb Mind instance is closed.")
        if self._loop is None:
            self._start_loop()
        assert self._loop is not None  # for type-checker
        future: Future[T] = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def _ensure_started(self) -> None:
        """Initialize storage / embedder / graph / searcher exactly once."""
        if self._started:
            return
        with self._start_lock:
            if self._started:
                return
            self._start_loop()
            self._run(self._async_start())
            self._started = True

    async def _async_start(self) -> None:
        """Mirror the storage + embedder + graph wiring of ``server/app.py``."""
        from hebb.embedding.factory import create_embedder
        from hebb.graph.knowledge_graph import KnowledgeGraph
        from hebb.retrieval.searcher import MemorySearcher
        from hebb.storage.factory import create_stores

        try:
            ctx = await create_stores(self.settings)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Failed to initialize storage backend: {exc}") from exc
        self._memory_store = ctx.memory_store
        self._partition_store = ctx.partition_store
        self._storage_close = ctx.close

        try:
            await ctx.partition_store.ensure_defaults()
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Failed to seed default partitions: {exc}") from exc

        try:
            embedder = await create_embedder(self.settings)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(f"Failed to initialize embedding provider: {exc}") from exc
        # Sync the dimension back onto settings the way server/app.py does
        # so that subsequent storage interactions see the correct value.
        self.settings.embedding_dim = embedder.dimension
        self._embedder = embedder

        kg_path_value = self.settings.kg_path
        self._knowledge_graph = KnowledgeGraph(Path(kg_path_value))
        self._searcher = MemorySearcher(store=ctx.memory_store, embedder=embedder, graph=self._knowledge_graph)

    def close(self) -> None:
        """Release storage handles, persist the knowledge graph, stop the loop.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        if self._closed:
            return
        try:
            if self._started:
                if self._knowledge_graph is not None:
                    try:
                        self._knowledge_graph.save()
                    except Exception:  # noqa: BLE001
                        logger.warning("Failed to save knowledge graph on close", exc_info=True)
                if self._storage_close is not None:
                    try:
                        self._run(self._storage_close())
                    except Exception:  # noqa: BLE001
                        logger.warning("Storage close raised", exc_info=True)
        finally:
            self._closed = True
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread is not None:
                self._loop_thread.join(timeout=5)

    # Context-manager protocol
    def __enter__(self) -> HebbMind:
        self._ensure_started()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover — best-effort
        try:
            self.close()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        content: str,
        *,
        partition: str = DEFAULT_PARTITION.value,
        importance: float = 5.0,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | MemoryMetadata | None = None,
        source: str | None = "library",
    ) -> Memory:
        """Persist a new memory and return the stored record.

        Args:
            content: The memory text. Required, 1–10000 characters.
            partition: Target partition id. Defaults to the
                ``mem_hippocampus`` working-memory inbox; consolidation
                will eventually migrate it to a long-term partition.
            importance: 0.0–10.0 importance score. Higher values resist
                forgetting longer.
            tags: Optional list of free-form tag strings.
            metadata: Either a :class:`MemoryMetadata` instance or a
                plain ``dict`` (will be coerced).
            source: Provenance label stored on the memory record.

        Returns:
            The full :class:`Memory` record, including its generated id.

        Raises:
            StorageError: If the backend write fails.
            EmbeddingError: If the embedder is enabled but fails.
        """
        self._ensure_started()
        meta = self._normalize_metadata(metadata)
        create = MemoryCreate(
            content=content,
            partition_id=partition,
            importance_score=importance,
            tags=list(tags) if tags else [],
            metadata=meta,
            source=source,
        )
        return self._run(self._async_add(create))

    async def _async_add(self, create: MemoryCreate) -> Memory:
        embedding: list[float] | None = None
        if self._embedder is not None:
            try:
                embedding = await self._embedder.embed(create.content)
            except Exception as exc:  # noqa: BLE001
                raise EmbeddingError(f"Embedding failed: {exc}") from exc
        try:
            return await self._memory_store.create(create, embedding=embedding)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Memory create failed: {exc}") from exc

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        partition_ids: list[str] | None = None,
        tags: list[str] | None = None,
        weight_recency: float = 1.0,
        weight_importance: float = 1.0,
        weight_relevance: float = 1.0,
    ) -> list[MemorySearchResult]:
        """Hybrid (vector + keyword + graph) search across memories.

        Args:
            query: Natural-language query string.
            top_k: Maximum number of scored results to return (1–100).
            partition_ids: Restrict search to these partitions. ``None``
                means "all partitions".
            tags: Optional tag filter; only memories whose tag set
                intersects ``tags`` are returned.
            weight_recency: Weight on the recency factor in the
                composite score.
            weight_importance: Weight on the importance factor.
            weight_relevance: Weight on the embedding/keyword relevance
                factor.

        Returns:
            A list of :class:`MemorySearchResult` objects sorted by
            descending composite score. Each result carries the
            underlying :class:`Memory`, the composite ``score``, and the
            three component scores (``recency_score``,
            ``importance_score_normalized``, ``relevance_score``).

        Raises:
            StorageError: If the backend search fails.
            EmbeddingError: If the embedder fails.
        """
        self._ensure_started()
        mq = MemoryQuery(
            query=query,
            partition_ids=partition_ids,
            tags=tags,
            top_k=top_k,
            weight_recency=weight_recency,
            weight_importance=weight_importance,
            weight_relevance=weight_relevance,
        )
        try:
            response = self._run(self._searcher.search(mq))
        except HebbMindError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Search failed: {exc}") from exc
        return response.results

    def get(self, memory_id: str) -> Memory:
        """Fetch a single memory by id.

        Args:
            memory_id: Id returned by :meth:`add` (or a search result).

        Returns:
            The :class:`Memory` record.

        Raises:
            MemoryNotFoundError: If no memory has this id.
            StorageError: On backend failure.
        """
        self._ensure_started()
        try:
            mem = self._run(self._memory_store.get(memory_id))
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Memory lookup failed: {exc}") from exc
        if mem is None:
            raise MemoryNotFoundError(f"No memory with id={memory_id!r}")
        return mem

    def delete(self, memory_id: str) -> None:
        """Delete a memory by id.

        Args:
            memory_id: Id of the memory to remove.

        Raises:
            MemoryNotFoundError: If no memory has this id.
            StorageError: On backend failure.
        """
        self._ensure_started()
        try:
            ok = self._run(self._memory_store.delete(memory_id))
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Memory delete failed: {exc}") from exc
        if not ok:
            raise MemoryNotFoundError(f"No memory with id={memory_id!r}")

    def list(
        self,
        *,
        partition: str | None = None,
        tags: list[str] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Memory], int]:
        """List memories with optional partition / tag filters.

        Args:
            partition: Restrict to a single partition id (e.g.
                ``"mem_preference"``). ``None`` means all partitions.
            tags: Tag intersection filter.
            offset: Pagination offset.
            limit: Page size (default 50).

        Returns:
            A ``(memories, total)`` tuple. ``total`` is the unpaginated
            row count (subject to the same caveats as the underlying
            backend — see audit notes on tag-pagination).

        Raises:
            StorageError: On backend failure.
        """
        self._ensure_started()
        try:
            return self._run(
                self._memory_store.list(
                    partition_id=partition,
                    tags=tags,
                    offset=offset,
                    limit=limit,
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Memory list failed: {exc}") from exc

    def consolidate(self, *, concurrency: int | None = None) -> _List[Any]:
        """Run one consolidation pass over the working-memory inbox.

        This mirrors what the scheduler invokes daily: pull every memory
        from the ``mem_hippocampus`` partition, group by ``session_id``,
        and ask the LLM to migrate them into long-term partitions.

        Args:
            concurrency: Override
                :attr:`Settings.consolidation_concurrency`.

        Returns:
            A list of ``ConsolidationResult`` records (one per processed
            memory). Empty list if no LLM is configured (the
            consolidation pipeline requires
            :attr:`Settings.llm_model`).

        Raises:
            LLMError: If the LLM pipeline fails.
        """
        self._ensure_started()
        if not self.settings.llm_model:
            logger.info("consolidate() skipped — settings.llm_model is unset.")
            return []
        try:
            return self._run(self._async_consolidate(concurrency))
        except HebbMindError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Consolidation failed: {exc}") from exc

    async def _async_consolidate(self, concurrency: int | None) -> _List[Any]:
        from hebb.scheduler.consolidation_job import run_consolidation

        assert self._knowledge_graph is not None, "consolidate requires _ensure_started()"
        assert self._embedder is not None, "consolidate requires _ensure_started()"
        return await run_consolidation(
            memory_store=self._memory_store,
            partition_store=self._partition_store,
            knowledge_graph=self._knowledge_graph,
            embedder=self._embedder,
            settings=self.settings,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_metadata(
        metadata: dict[str, Any] | MemoryMetadata | None,
    ) -> MemoryMetadata:
        if metadata is None:
            return MemoryMetadata()
        if isinstance(metadata, MemoryMetadata):
            return metadata
        return MemoryMetadata(**metadata)


__all__ = ["HebbMind"]
