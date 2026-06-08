"""Hebb Mind — Neuroscience-inspired memory framework for AI agents.

Public surface
--------------

>>> from hebb import HebbMind
>>> hc = HebbMind()
>>> hc.add("user prefers dark mode", partition="mem_preference")
>>> for r in hc.search("appearance preferences", top_k=5):
...     print(r.score, r.memory.content)
>>> hc.close()

The :class:`HebbMind` facade is the recommended entry point for
library users. It wires storage, embedding, knowledge graph, and search
into a single synchronous handle.

For HTTP / MCP / CLI usage, see :mod:`hebb.server`,
:mod:`hebb.mcp`, and :mod:`hebb.cli`.

Heavy dependencies (``sentence_transformers``, ``litellm``, FastAPI…)
are **not** imported at package-import time. They are loaded lazily on
first use — typically when you construct a :class:`HebbMind`
instance — so ``import hebb`` stays sub-second.
"""

from __future__ import annotations

# Side-effect-only import: must run before any sqlite usage. Keep first.
import hebb.storage._sqlite_compat  # noqa: F401

from typing import TYPE_CHECKING, Any

from hebb.exceptions import (
    ConfigError,
    EmbeddingError,
    HebbMindError,
    LLMError,
    MemoryNotFoundError,
    StorageError,
)

# Bumped MANUALLY on release (release-please automation removed). Keep in sync
# with the version in pyproject.toml, .release-please-manifest.json, and
# .claude-plugin/plugin.json.
__version__ = "0.1.7"

# ``HebbMind`` pulls in storage + embedding + graph + searcher, which
# in turn import heavy third-party libs (sentence-transformers, litellm,
# numpy …). Defer the import until first attribute access so that the
# bare ``import hebb`` is cheap.
if TYPE_CHECKING:  # pragma: no cover
    from hebb.api import HebbMind  # noqa: F401


def __getattr__(name: str) -> Any:
    """Lazy-load the public :class:`HebbMind` facade on first access."""
    if name == "HebbMind":
        from hebb.api import HebbMind as _HebbMind

        globals()["HebbMind"] = _HebbMind
        return _HebbMind
    raise AttributeError(f"module 'hebb' has no attribute {name!r}")


__all__ = [
    "__version__",
    "HebbMind",
    "HebbMindError",
    "ConfigError",
    "StorageError",
    "EmbeddingError",
    "LLMError",
    "MemoryNotFoundError",
]
