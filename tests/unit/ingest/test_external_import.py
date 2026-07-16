"""Tests for deterministic external Markdown memory imports."""

from __future__ import annotations

from pathlib import Path

import pytest

from hebb import HebbMind
from hebb.config.settings import Settings
from hebb.constants import PartitionType
from hebb.ingest.external import discover_external_entries, import_external_corpus

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "external"


@pytest.mark.parametrize(
    ("source", "expected_count"),
    [("openhands", 2), ("openclaw", 4), ("hkuds", 2)],
)
def test_discover_external_entries_uses_fixture_layouts(source: str, expected_count: int) -> None:
    entries = discover_external_entries(source, FIXTURES / source)

    assert len(entries) == expected_count
    assert all(entry.content for entry in entries)
    assert all("external-memory" in entry.tags for entry in entries)
    assert all(entry.metadata["external_source"] == source for entry in entries)


def test_openhands_entries_are_cleaned_and_procedural() -> None:
    entries = discover_external_entries("openhands", FIXTURES / "openhands")

    assert {entry.partition for entry in entries} == {PartitionType.PROCEDURAL.value}
    combined = "\n".join(entry.content for entry in entries)
    assert "fenced example" not in combined
    assert "system-reminder" not in combined
    assert "typed public functions" in combined


def test_openclaw_routes_workspace_documents() -> None:
    entries = discover_external_entries("openclaw", FIXTURES / "openclaw")
    partitions = {entry.source_path: entry.partition for entry in entries}

    assert partitions["USER.md"] == PartitionType.PREFERENCE.value
    assert partitions["SOUL.md"] == PartitionType.PROCEDURAL.value
    assert partitions["MEMORY.md"] == PartitionType.HIPPOCAMPUS.value
    assert partitions["memory/2026-07-14.md"] == PartitionType.EPISODIC.value


def test_hkuds_uses_schema_v1_metadata_and_skips_index_and_disabled() -> None:
    entries = discover_external_entries("hkuds", FIXTURES / "hkuds")
    by_path = {entry.source_path: entry for entry in entries}

    assert set(by_path) == {
        ".openharness/memory/project-layout.md",
        ".openharness/memory/review-workflow.md",
    }
    assert by_path[".openharness/memory/project-layout.md"].partition == PartitionType.SEMANTIC.value
    assert by_path[".openharness/memory/project-layout.md"].importance == 8.0
    assert by_path[".openharness/memory/review-workflow.md"].partition == PartitionType.PROCEDURAL.value
    assert by_path[".openharness/memory/project-layout.md"].metadata["external_native_id"] == "mem-project-layout"


@pytest.mark.parametrize(
    ("source", "expected_count", "query", "content_prefix"),
    [
        ("openhands", 2, "typed public functions", "# Python Guidelines"),
        ("openclaw", 4, "dark mode", "# User Profile"),
        ("hkuds", 2, "persistence adapters", "# Project Layout"),
    ],
)
def test_import_is_idempotent_and_populates_search_indexes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    expected_count: int,
    query: str,
    content_prefix: str,
) -> None:
    class FixedEmbedder:
        @property
        def dimension(self) -> int:
            return 384

        async def embed(self, _text: str) -> list[float]:
            return [0.01] * self.dimension

        async def embed_batch(self, texts: list[str]) -> list[list[float]]:
            return [[0.01] * self.dimension for _ in texts]

        async def aclose(self) -> None:
            return None

    async def fake_create_embedder(_settings: Settings) -> FixedEmbedder:
        return FixedEmbedder()

    monkeypatch.setattr("hebb.embedding.factory.create_embedder", fake_create_embedder)
    settings = Settings(home_dir=tmp_path, storage_type="sqlite", embedding_enabled=True, embedding_dim=384)

    with HebbMind(config=settings) as mind:
        first = import_external_corpus(source, FIXTURES / source, mind)
        second = import_external_corpus(source, FIXTURES / source, mind)

        assert first.imported == expected_count
        assert first.skipped_existing == 0
        assert second.imported == 0
        assert second.skipped_existing == expected_count
        memories, total = mind.list()
        assert total == expected_count
        assert len({memory.metadata.model_dump()["external_key"] for memory in memories}) == expected_count
        assert any(hit.memory.content.startswith(content_prefix) for hit in mind.search(query, top_k=5))

        async def index_counts() -> tuple[int, int]:
            store = mind._memory_store  # noqa: SLF001 - integration assertion on persistence side effects
            embedding_cursor = await store.db.execute("SELECT COUNT(*) FROM memory_embeddings")
            fts_cursor = await store.db.execute("SELECT COUNT(*) FROM memory_fts")
            embedding_row = await embedding_cursor.fetchone()
            fts_row = await fts_cursor.fetchone()
            return int(embedding_row[0]), int(fts_row[0])

        embedding_count, fts_count = mind._run(index_counts())  # noqa: SLF001
        assert embedding_count == expected_count
        assert fts_count == expected_count
