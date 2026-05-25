"""Stdio protection utilities for MCP transport safety."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager

# Saved real stdout file descriptor (set by capture_stdout).
_real_stdout_fd: int | None = None


def capture_stdout() -> None:
    """Redirect fd 1 to stderr so stray prints cannot corrupt MCP stdio.

    Call at module scope, BEFORE any heavy third-party imports.
    Pair with :func:`restore_stdout` before starting the MCP event loop.
    """
    global _real_stdout_fd
    try:
        _real_stdout_fd = os.dup(1)
        os.dup2(sys.stderr.fileno(), 1)
    except (OSError, AttributeError):
        _real_stdout_fd = None
        return
    sys.stdout = sys.stderr


def restore_stdout() -> None:
    """Restore the real stdout fd saved by :func:`capture_stdout`.

    Safe to call even if ``capture_stdout`` was never called (no-op).
    """
    global _real_stdout_fd
    if _real_stdout_fd is None:
        return
    try:
        os.dup2(_real_stdout_fd, 1)
        os.close(_real_stdout_fd)
    except OSError:
        pass
    sys.stdout = open(1, "w", closefd=False)  # noqa: SIM115
    _real_stdout_fd = None


@contextmanager
def suppress_stdout_stderr() -> Generator[None, None, None]:
    """Silence both stdout and stderr at the fd level.

    Useful for noisy library init (e.g. SentenceTransformer loading).
    """
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stdout_fd = os.dup(1)
    old_stderr_fd = os.dup(2)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    try:
        yield
    finally:
        os.dup2(old_stdout_fd, 1)
        os.dup2(old_stderr_fd, 2)
        os.close(old_stdout_fd)
        os.close(old_stderr_fd)
        os.close(devnull)
