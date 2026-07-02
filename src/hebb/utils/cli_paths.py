"""Resolve absolute argv for the ``hebb`` and ``hebb-mcp`` console scripts.

Why this exists
---------------
``pip install --user`` puts entry-point scripts in a per-user bin dir
that is **not** on the default macOS PATH (and is hit-or-miss elsewhere
when subprocesses are launched from a GUI app — Claude Code's hooks and
MCP launches, the launchd / systemd / Task Scheduler service, etc.).

Anything we write into another tool's config (Claude Code hooks,
``claude mcp add``, launchd plist, …) must therefore use an **absolute**
command — never a bare ``hebb`` / ``hebb-mcp`` that depends on the
caller's PATH.

Resolution order, identical for both helpers:
  1. ``shutil.which(name)`` — picks up pipx, venv, ``--user`` install,
     system install. This is the path the user is actually running.
  2. Fallback to ``[sys.executable, '-m', '<module>']`` — works even if
     entry-point scripts were stripped (zipapp, vendored install, etc.).
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path


def hebb_command() -> list[str]:
    """Absolute argv to invoke the ``hebb`` CLI."""
    source_cmd = _source_checkout_command("hebb.cli.main")
    if source_cmd:
        return source_cmd
    found = shutil.which("hebb")
    if found:
        return [found]
    return [sys.executable, "-m", "hebb.cli.main"]


def hebb_mcp_command() -> list[str]:
    """Absolute argv to invoke the ``hebb-mcp`` stdio server."""
    source_cmd = _source_checkout_command("hebb.mcp.server")
    if source_cmd:
        return source_cmd
    found = shutil.which("hebb-mcp")
    if found:
        return [found]
    return [sys.executable, "-m", "hebb.mcp.server"]


def shell_quote(argv: list[str]) -> str:
    """Shell-safe single string for tools that take a `command` string field.

    Used by Claude Code hooks (`settings.json -> hooks[].hooks[].command`)
    which is executed via ``/bin/sh -c``.
    """
    return shlex.join(argv)


def _source_checkout_command(module: str) -> list[str] | None:
    """Return a source-checkout command when running from this repository.

    Args:
        module: Python module to execute with ``-m``.

    Returns:
        Command argv with ``PYTHONPATH`` pointed at the checkout's ``src``
        directory, or ``None`` when the current command is not being run from
        this source tree.
    """
    root = _source_checkout_root()
    if root is None:
        return None
    src = root / "src"
    python = _preferred_python(root)
    if os.name == "nt":
        return [str(python), "-m", module]
    return ["/usr/bin/env", f"PYTHONPATH={src}", str(python), "-m", module]


def _source_checkout_root() -> Path | None:
    """Resolve the repository root when the process is inside this checkout."""
    src = Path(__file__).resolve().parents[2]
    root = src.parent
    cwd = Path.cwd().resolve()
    if not (root / "pyproject.toml").is_file():
        return None
    if not (src / "hebb" / "cli" / "main.py").is_file():
        return None
    if cwd == root or root in cwd.parents:
        return root
    return None


def _preferred_python(root: Path) -> Path:
    """Pick the Python executable most likely to have checkout dependencies."""
    venv_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.is_file():
        return venv_python
    return Path(sys.executable)
