"""Tests for Claude Code file-based memory discovery and the console router."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hebb.integrations.claude_code import memory_docs


@pytest.fixture
def claude_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the module at an isolated, empty Claude home for each test."""
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    return home


def _make_project(home: Path, slug: str, files: dict[str, str]) -> Path:
    mem = home / "projects" / slug / "memory"
    mem.mkdir(parents=True)
    for name, content in files.items():
        (mem / name).write_text(content, encoding="utf-8")
    return mem


class TestClaudeHome:
    def test_honors_config_dir_override(self, claude_home: Path) -> None:
        assert memory_docs.claude_home() == claude_home
        assert memory_docs.projects_root() == claude_home / "projects"

    def test_defaults_to_dot_claude(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        assert memory_docs.claude_home() == Path.home() / ".claude"


class TestListProjects:
    def test_empty_when_no_projects_root(self, claude_home: Path) -> None:
        assert memory_docs.list_projects() == []

    def test_skips_dirs_without_memory(self, claude_home: Path) -> None:
        (claude_home / "projects" / "-no-memory").mkdir(parents=True)
        _make_project(claude_home, "-with-memory", {"MEMORY.md": "# index\n"})
        slugs = [p.slug for p in memory_docs.list_projects()]
        assert slugs == ["-with-memory"]

    def test_skips_memory_dir_without_md_files(self, claude_home: Path) -> None:
        mem = claude_home / "projects" / "-empty" / "memory"
        mem.mkdir(parents=True)
        (mem / "notes.txt").write_text("not markdown")
        assert memory_docs.list_projects() == []

    def test_reports_counts_and_index_flag(self, claude_home: Path) -> None:
        _make_project(
            claude_home,
            "-proj",
            {"MEMORY.md": "# index\n", "note-a.md": "a", "note-b.md": "b"},
        )
        projects = memory_docs.list_projects()
        assert len(projects) == 1
        proj = projects[0]
        assert proj.slug == "-proj"
        assert proj.file_count == 3
        assert proj.has_index is True

    def test_orders_by_recency(self, claude_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        old = _make_project(claude_home, "-old", {"MEMORY.md": "old"})
        new = _make_project(claude_home, "-new", {"MEMORY.md": "new"})
        import os

        os.utime(old / "MEMORY.md", (1000, 1000))
        os.utime(new / "MEMORY.md", (2000, 2000))
        slugs = [p.slug for p in memory_docs.list_projects()]
        assert slugs == ["-new", "-old"]


class TestListFiles:
    def test_index_listed_first(self, claude_home: Path) -> None:
        _make_project(
            claude_home,
            "-proj",
            {"zeta.md": "z", "MEMORY.md": "i", "alpha.md": "a"},
        )
        names = [f.name for f in memory_docs.list_files("-proj")]
        assert names == ["MEMORY.md", "alpha.md", "zeta.md"]

    def test_empty_for_unknown_project(self, claude_home: Path) -> None:
        assert memory_docs.list_files("-does-not-exist") == []


class TestReadWrite:
    def test_read_returns_content(self, claude_home: Path) -> None:
        _make_project(claude_home, "-proj", {"note.md": "hello world"})
        content, st = memory_docs.read_file("-proj", "note.md")
        assert content == "hello world"
        assert st.st_size == len("hello world")

    def test_read_missing_raises(self, claude_home: Path) -> None:
        _make_project(claude_home, "-proj", {"note.md": "x"})
        with pytest.raises(FileNotFoundError):
            memory_docs.read_file("-proj", "absent.md")

    def test_write_overwrites_existing(self, claude_home: Path) -> None:
        mem = _make_project(claude_home, "-proj", {"note.md": "old"})
        memory_docs.write_file("-proj", "note.md", "new content")
        assert (mem / "note.md").read_text() == "new content"

    def test_write_missing_file_raises(self, claude_home: Path) -> None:
        _make_project(claude_home, "-proj", {"note.md": "x"})
        with pytest.raises(FileNotFoundError):
            memory_docs.write_file("-proj", "brand-new.md", "data")

    def test_write_does_not_create_new_files(self, claude_home: Path) -> None:
        mem = _make_project(claude_home, "-proj", {"note.md": "x"})
        with pytest.raises(FileNotFoundError):
            memory_docs.write_file("-proj", "evil.md", "data")
        assert not (mem / "evil.md").exists()


class TestPathSafety:
    @pytest.mark.parametrize("slug", ["", ".", "..", "a/b", "..\\b", "x\x00y"])
    def test_unsafe_slug_rejected(self, claude_home: Path, slug: str) -> None:
        with pytest.raises(memory_docs.UnsafePathError):
            memory_docs.list_files(slug)

    @pytest.mark.parametrize(
        "name",
        ["../secret.md", "..%2f.md", "sub/dir.md", "note.txt", "settings.json", "a\x00.md", "no-extension"],
    )
    def test_unsafe_name_rejected(self, claude_home: Path, name: str) -> None:
        _make_project(claude_home, "-proj", {"note.md": "x"})
        with pytest.raises(memory_docs.UnsafePathError):
            memory_docs.read_file("-proj", name)

    def test_traversal_cannot_escape_memory_dir(self, claude_home: Path) -> None:
        # A secret outside the memory dir must stay unreachable even though
        # the file genuinely exists.
        secret = claude_home / "projects" / "-proj" / "secret.md"
        _make_project(claude_home, "-proj", {"note.md": "x"})
        secret.write_text("classified")
        with pytest.raises(memory_docs.UnsafePathError):
            memory_docs.read_file("-proj", "../secret.md")


@pytest.fixture
def client() -> TestClient:
    from hebb.server.routers import claude_memory

    app = FastAPI()
    app.include_router(claude_memory.router, prefix="/api/v1/claude-memory")
    return TestClient(app)


class TestRouter:
    def test_list_projects_endpoint(self, claude_home: Path, client: TestClient) -> None:
        _make_project(claude_home, "-proj", {"MEMORY.md": "# i\n", "n.md": "x"})
        resp = client.get("/api/v1/claude-memory/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["slug"] == "-proj"
        assert data[0]["file_count"] == 2
        assert data[0]["has_index"] is True

    def test_list_files_endpoint(self, claude_home: Path, client: TestClient) -> None:
        _make_project(claude_home, "-proj", {"MEMORY.md": "i", "a.md": "a"})
        resp = client.get("/api/v1/claude-memory/files", params={"project": "-proj"})
        assert resp.status_code == 200
        assert [f["name"] for f in resp.json()] == ["MEMORY.md", "a.md"]

    def test_read_file_endpoint(self, claude_home: Path, client: TestClient) -> None:
        _make_project(claude_home, "-proj", {"note.md": "body text"})
        resp = client.get("/api/v1/claude-memory/file", params={"project": "-proj", "name": "note.md"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "body text"

    def test_read_missing_returns_404(self, claude_home: Path, client: TestClient) -> None:
        _make_project(claude_home, "-proj", {"note.md": "x"})
        resp = client.get("/api/v1/claude-memory/file", params={"project": "-proj", "name": "absent.md"})
        assert resp.status_code == 404

    def test_traversal_returns_400(self, claude_home: Path, client: TestClient) -> None:
        _make_project(claude_home, "-proj", {"note.md": "x"})
        resp = client.get(
            "/api/v1/claude-memory/file",
            params={"project": "-proj", "name": "../note.md"},
        )
        assert resp.status_code == 400

    def test_write_roundtrip_endpoint(self, claude_home: Path, client: TestClient) -> None:
        mem = _make_project(claude_home, "-proj", {"note.md": "old"})
        resp = client.put(
            "/api/v1/claude-memory/file",
            json={"project": "-proj", "name": "note.md", "content": "fresh"},
        )
        assert resp.status_code == 200
        assert (mem / "note.md").read_text() == "fresh"

    def test_write_missing_returns_404(self, claude_home: Path, client: TestClient) -> None:
        _make_project(claude_home, "-proj", {"note.md": "x"})
        resp = client.put(
            "/api/v1/claude-memory/file",
            json={"project": "-proj", "name": "new.md", "content": "data"},
        )
        assert resp.status_code == 404
