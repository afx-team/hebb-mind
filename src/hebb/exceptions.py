"""Custom exception hierarchy for the Hebb Mind library.

All exceptions raised by the public Python facade derive from
:class:`HebbMindError`, so library users can write::

    try:
        hc.add("…")
    except HebbMindError:
        ...

and catch every framework-originated failure with one ``except``.

.. note::
   This module exposes the hierarchy but **does not yet refactor existing
   internals to raise these types**. Storage / embedding / agent layers
   still raise stdlib exceptions (``ValueError``, ``KeyError``,
   ``FileNotFoundError`` …). Future PRs will gradually adopt these classes
   inside the lower layers; the public facade in
   :mod:`hebb.api` already translates the most common stdlib
   failures into the appropriate subclass where it has enough context.
"""

from __future__ import annotations


class HebbMindError(Exception):
    """Base class for every Hebb Mind-originated exception.

    Catch this if you want to handle *any* framework failure without
    distinguishing between subsystems.
    """


class ConfigError(HebbMindError):
    """Configuration loading or validation failed.

    Raised when ``hebb.json`` cannot be parsed, a referenced
    workspace is invalid, or a required field is missing.
    """


class StorageError(HebbMindError):
    """A storage backend (SQLite, PostgreSQL, …) raised an error.

    Wraps connection failures, schema-init failures, and unexpected
    backend exceptions surfaced through the :class:`MemoryStore`
    protocol.
    """


class EmbeddingError(HebbMindError):
    """An embedding provider failed to produce a vector.

    Raised for both local (``sentence-transformers``) and API
    (``litellm``) providers — model load failures, network errors,
    dimension mismatches.
    """


class LLMError(HebbMindError):
    """LiteLLM / consolidation pipeline failure.

    Raised when an LLM call fails inside a recall, consolidation, or
    other agent path. Includes JSON-parse failures from
    :class:`hebb.agents.llm_client.LLMClient`.
    """


class MemoryNotFoundError(HebbMindError):
    """A memory id was referenced but does not exist in the store.

    Raised by :meth:`HebbMind.get` and :meth:`HebbMind.delete`
    when ``memory_id`` is unknown.
    """


__all__ = [
    "HebbMindError",
    "ConfigError",
    "StorageError",
    "EmbeddingError",
    "LLMError",
    "MemoryNotFoundError",
]
