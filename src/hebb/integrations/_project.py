"""Detect the code project a hook/MCP call originated from."""

from __future__ import annotations

from pathlib import Path


def detect_project_name(start: str | Path | None = None) -> str | None:
    """Return the name of the nearest ancestor directory containing ``.git``.

    Walks up from ``start`` (or the current working directory) and returns
    that directory's name. Returns ``None`` if no ``.git`` is found before
    the filesystem root.
    """
    try:
        p = Path(start).resolve() if start else Path.cwd()
    except (OSError, RuntimeError):
        return None
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            return parent.name
    return None
