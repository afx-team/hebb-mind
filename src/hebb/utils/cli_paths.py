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

import shlex
import shutil
import sys


def hebb_command() -> list[str]:
    """Absolute argv to invoke the ``hebb`` CLI."""
    found = shutil.which("hebb")
    if found:
        return [found]
    return [sys.executable, "-m", "hebb.cli.main"]


def hebb_mcp_command() -> list[str]:
    """Absolute argv to invoke the ``hebb-mcp`` stdio server."""
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
