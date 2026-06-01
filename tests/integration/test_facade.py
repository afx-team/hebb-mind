"""Smoke tests for the synchronous Hebb Mind facade.

These tests intentionally avoid network calls. They construct a
``HebbMind`` against a tmp_path SQLite workspace; the local embedder
is loaded only if the default sentence-transformers model is already
cached on disk (otherwise the tests are skipped, not failed).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hebb import (
    ConfigError,
    EmbeddingError,
    HebbMind,
    HebbMindError,
    LLMError,
    MemoryNotFoundError,
    StorageError,
    __version__,
)
from hebb.config.settings import Settings

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _local_model_available() -> bool:
    """True if the default sentence-transformers model is cached locally."""
    try:
        from hebb.embedding.local import is_model_cached

        return bool(is_model_cached("all-MiniLM-L6-v2"))
    except Exception:
        return False


def _make_settings(tmp_path: Path, *, embeddings: bool) -> Settings:
    """Build an in-tmp Settings instance for a single test."""
    return Settings(
        home_dir=tmp_path,
        storage_type="sqlite",
        embedding_enabled=embeddings,
    )


def _make_hebb(tmp_path: Path, *, embeddings: bool = False) -> HebbMind:
    """Construct a Hebb Mind pinned to ``tmp_path``."""
    settings = _make_settings(tmp_path, embeddings=embeddings)
    return HebbMind(config=settings)


# ----------------------------------------------------------------------
# Public-surface checks
# ----------------------------------------------------------------------


def test_public_exports_present() -> None:
    """All advertised symbols are importable from the package root."""
    import hebb

    for name in [
        "HebbMind",
        "HebbMindError",
        "ConfigError",
        "StorageError",
        "EmbeddingError",
        "LLMError",
        "MemoryNotFoundError",
        "__version__",
    ]:
        assert hasattr(hebb, name), f"missing public symbol: {name}"


def test_exception_hierarchy() -> None:
    """All custom exceptions derive from HebbMindError."""
    for cls in (ConfigError, StorageError, EmbeddingError, LLMError, MemoryNotFoundError):
        assert issubclass(cls, HebbMindError)


def test_version_matches_pyproject() -> None:
    """``__version__`` must match the version pinned in ``pyproject.toml``."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)

    assert __version__ == data["project"]["version"], (
        f"hebb.__version__ = {__version__!r} but "
        f"pyproject.toml = {data['project']['version']!r}"
    )


# ----------------------------------------------------------------------
# Facade behavior — embedding-disabled (always-on tests)
# ----------------------------------------------------------------------


def test_facade_context_manager(tmp_path: Path) -> None:
    """``with HebbMind()`` cleanly opens and closes the instance."""
    settings = _make_settings(tmp_path, embeddings=False)
    with HebbMind(config=settings) as hc:
        assert hc.settings is settings
        assert hc._started  # noqa: SLF001 — internal smoke check
    assert hc._closed  # noqa: SLF001


def test_facade_rejects_double_config(tmp_path: Path) -> None:
    """Passing both ``config`` and ``config_path`` is a ConfigError."""
    settings = _make_settings(tmp_path, embeddings=False)
    with pytest.raises(ConfigError):
        HebbMind(config=settings, config_path=tmp_path / "x.json")


def test_facade_get_missing_raises(tmp_path: Path) -> None:
    """``get`` on an unknown id raises ``MemoryNotFoundError``."""
    with _make_hebb(tmp_path) as hc:
        with pytest.raises(MemoryNotFoundError):
            hc.get("does-not-exist")


@pytest.mark.skipif(
    not _local_model_available(),
    reason="default sentence-transformers model is not cached locally "
    "(SQLite delete touches memory_embeddings which only exists when "
    "embeddings are enabled)",
)
def test_facade_delete_missing_raises(tmp_path: Path) -> None:
    """``delete`` on an unknown id raises ``MemoryNotFoundError``."""
    with _make_hebb(tmp_path, embeddings=True) as hc:
        with pytest.raises(MemoryNotFoundError):
            hc.delete("does-not-exist")


def test_facade_list_empty(tmp_path: Path) -> None:
    """A fresh workspace lists zero memories."""
    with _make_hebb(tmp_path) as hc:
        memories, total = hc.list()
        assert memories == []
        assert total == 0


def test_facade_consolidate_noop_without_llm(tmp_path: Path) -> None:
    """``consolidate()`` is a graceful no-op when no LLM key is set."""
    with _make_hebb(tmp_path) as hc:
        assert hc.settings.llm_model is None
        assert hc.consolidate() == []


def test_facade_add_and_list_without_embedding(tmp_path: Path) -> None:
    """Add → list roundtrip works even with embeddings disabled."""
    with _make_hebb(tmp_path) as hc:
        memory = hc.add("user prefers dark mode", partition="mem_preference")
        assert memory.id
        assert memory.content == "user prefers dark mode"
        assert memory.partition_id == "mem_preference"

        memories, total = hc.list(partition="mem_preference")
        assert total == 1
        assert memories[0].id == memory.id


@pytest.mark.skipif(
    not _local_model_available(),
    reason="default sentence-transformers model is not cached locally "
    "(SQLite delete touches memory_embeddings which only exists when "
    "embeddings are enabled)",
)
def test_facade_add_and_delete(tmp_path: Path) -> None:
    """Add → get → delete → get-raises lifecycle."""
    with _make_hebb(tmp_path, embeddings=True) as hc:
        memory = hc.add("ephemeral note")
        assert hc.get(memory.id).id == memory.id
        hc.delete(memory.id)
        with pytest.raises(MemoryNotFoundError):
            hc.get(memory.id)


# ----------------------------------------------------------------------
# Facade behavior — embedding-enabled (skipped if model not cached)
# ----------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(
    not _local_model_available(),
    reason="default sentence-transformers model is not cached locally",
)
def test_facade_add_and_search_roundtrip(tmp_path: Path) -> None:
    """Vector search returns the memory we just added."""
    with _make_hebb(tmp_path, embeddings=True) as hc:
        added = hc.add("the user prefers dark mode in their editor")
        results = hc.search("user style preferences", top_k=5)
        assert results, "expected at least one search result"
        ids = {r.memory.id for r in results}
        assert added.id in ids


@pytest.mark.slow
@pytest.mark.skipif(
    not _local_model_available(),
    reason="default sentence-transformers model is not cached locally",
)
def test_facade_delete_then_search_returns_nothing(tmp_path: Path) -> None:
    """After deletion, the memory disappears from search."""
    with _make_hebb(tmp_path, embeddings=True) as hc:
        added = hc.add("temporary memory about purple elephants")
        hc.delete(added.id)
        results = hc.search("purple elephants", top_k=10)
        assert added.id not in {r.memory.id for r in results}


# Silence "unused import" warnings — the symbols above are the
# package-export contract under test.
_ = (StorageError, EmbeddingError, LLMError)
