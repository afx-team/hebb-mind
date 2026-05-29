"""Discover and edit Claude Code's file-based memory documents.

Claude Code keeps a per-project "auto memory" as Markdown under
``<claude_home>/projects/<slug>/memory/`` — a ``MEMORY.md`` index plus the
linked note files it references. This module locates those documents and
exposes sandboxed read/write access so the web console can surface them
alongside Hebb Mind's own DB-backed memories.

Every path derived from caller-supplied input (``project`` slug,
``name`` filename) is validated and confined to the memory directory; an
:class:`UnsafePathError` is raised for anything that would escape it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_INDEX_NAME = "MEMORY.md"


class UnsafePathError(ValueError):
    """Raised when a caller-supplied slug or filename escapes the sandbox."""


@dataclass(frozen=True)
class MemoryProject:
    """A Claude Code project that has a non-empty ``memory/`` directory."""

    slug: str
    path: str
    file_count: int
    has_index: bool
    updated_at: float


@dataclass(frozen=True)
class MemoryFile:
    """A single Markdown memory document inside a project."""

    name: str
    size: int
    updated_at: float
    is_index: bool


def claude_home() -> Path:
    """Return the Claude Code config directory.

    Honors ``CLAUDE_CONFIG_DIR`` (the same override Claude Code itself
    respects) and falls back to ``~/.claude``.

    Returns:
        Absolute path to the Claude Code config directory.
    """
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def projects_root() -> Path:
    """Return the ``projects/`` directory under the Claude Code home."""
    return claude_home() / "projects"


def _prettify_slug(slug: str) -> str:
    """Best-effort reconstruction of a project's real path from its slug.

    Claude Code derives the slug as ``abs_path.replace("/", "-")``; the
    reverse is ambiguous when a directory name itself contains ``-``. We
    only use the reconstructed path when it actually exists on disk,
    otherwise we return the slug unchanged.

    Args:
        slug: The project directory name under ``projects/``.

    Returns:
        A human-readable path when one can be confirmed, else the slug.
    """
    candidate = slug.replace("-", "/")
    if candidate.startswith("/") and Path(candidate).is_dir():
        return candidate
    return slug


def _validate_slug(slug: str) -> str:
    """Reject a project slug that contains path separators or traversal.

    Args:
        slug: Caller-supplied project directory name.

    Returns:
        The slug unchanged when it is safe.

    Raises:
        UnsafePathError: When the slug is empty or could escape ``projects/``.
    """
    if not slug or slug in (".", "..") or "/" in slug or "\\" in slug or "\x00" in slug:
        raise UnsafePathError(f"invalid project slug: {slug!r}")
    return slug


def _memory_dir(slug: str) -> Path:
    """Return the validated ``memory/`` directory for a project slug.

    Args:
        slug: Caller-supplied project directory name.

    Returns:
        Resolved absolute path to the project's ``memory/`` directory.

    Raises:
        UnsafePathError: When the resolved path escapes ``projects/``.
    """
    _validate_slug(slug)
    root = projects_root().resolve()
    mem_dir = (root / slug / "memory").resolve()
    if not mem_dir.is_relative_to(root):
        raise UnsafePathError(f"project escapes projects root: {slug!r}")
    return mem_dir


def _safe_file_path(slug: str, name: str) -> Path:
    """Return the validated absolute path to a memory file.

    Args:
        slug: Caller-supplied project directory name.
        name: Caller-supplied Markdown filename (no directory component).

    Returns:
        Resolved absolute path inside the project's ``memory/`` directory.

    Raises:
        UnsafePathError: When ``name`` is not a bare ``.md`` filename or the
            resolved path escapes the memory directory.
    """
    if not name.endswith(".md") or "/" in name or "\\" in name or ".." in name or "\x00" in name:
        raise UnsafePathError(f"invalid memory file name: {name!r}")
    mem_dir = _memory_dir(slug)
    path = (mem_dir / name).resolve()
    if not path.is_relative_to(mem_dir):
        raise UnsafePathError(f"file escapes memory dir: {name!r}")
    return path


def list_projects() -> list[MemoryProject]:
    """Scan all Claude Code projects that have memory documents.

    Returns:
        Projects with a non-empty ``memory/`` directory, most recently
        modified first.
    """
    root = projects_root()
    if not root.is_dir():
        return []

    projects: list[MemoryProject] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        mem_dir = child / "memory"
        if not mem_dir.is_dir():
            continue
        md_files = [f for f in mem_dir.glob("*.md") if f.is_file()]
        if not md_files:
            continue
        latest = max(f.stat().st_mtime for f in md_files)
        projects.append(
            MemoryProject(
                slug=child.name,
                path=_prettify_slug(child.name),
                file_count=len(md_files),
                has_index=(mem_dir / _INDEX_NAME).is_file(),
                updated_at=latest,
            )
        )

    projects.sort(key=lambda p: p.updated_at, reverse=True)
    return projects


def list_files(slug: str) -> list[MemoryFile]:
    """List the Markdown memory documents in a project.

    Args:
        slug: Project directory name under ``projects/``.

    Returns:
        Memory files with ``MEMORY.md`` first, then alphabetical.

    Raises:
        UnsafePathError: When ``slug`` is unsafe.
    """
    mem_dir = _memory_dir(slug)
    if not mem_dir.is_dir():
        return []

    files: list[MemoryFile] = []
    for path in mem_dir.glob("*.md"):
        if not path.is_file():
            continue
        st = path.stat()
        files.append(
            MemoryFile(
                name=path.name,
                size=st.st_size,
                updated_at=st.st_mtime,
                is_index=(path.name == _INDEX_NAME),
            )
        )

    files.sort(key=lambda f: (not f.is_index, f.name.lower()))
    return files


def read_file(slug: str, name: str) -> tuple[str, os.stat_result]:
    """Read a memory document's content.

    Args:
        slug: Project directory name under ``projects/``.
        name: Markdown filename within the project's ``memory/`` directory.

    Returns:
        A ``(content, stat)`` tuple.

    Raises:
        UnsafePathError: When ``slug`` or ``name`` is unsafe.
        FileNotFoundError: When the file does not exist.
    """
    path = _safe_file_path(slug, name)
    if not path.is_file():
        raise FileNotFoundError(name)
    return path.read_text(encoding="utf-8"), path.stat()


def write_file(slug: str, name: str, content: str) -> os.stat_result:
    """Overwrite an existing memory document.

    Writing is restricted to files that already exist so the console can
    only edit memories, not create arbitrary files on disk.

    Args:
        slug: Project directory name under ``projects/``.
        name: Markdown filename within the project's ``memory/`` directory.
        content: New file content (UTF-8).

    Returns:
        The post-write ``stat`` of the file.

    Raises:
        UnsafePathError: When ``slug`` or ``name`` is unsafe.
        FileNotFoundError: When the target file does not already exist.
    """
    path = _safe_file_path(slug, name)
    if not path.is_file():
        raise FileNotFoundError(name)
    path.write_text(content, encoding="utf-8")
    return path.stat()
