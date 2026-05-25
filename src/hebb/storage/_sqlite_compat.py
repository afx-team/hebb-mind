"""Ensure the ``sqlite3`` module supports extension loading.

On platforms where the stdlib ``sqlite3`` is compiled without
``--enable-loadable-extensions`` (notably macOS python.org builds),
we swap in ``pysqlite3`` as a transparent drop-in replacement
via ``sys.modules`` **before** any other module (especially ``aiosqlite``)
imports ``sqlite3``.

This module must be imported as early as possible — ideally from
``hebb/__init__.py``.
"""

from __future__ import annotations

import logging
import sqlite3
import sys

logger = logging.getLogger(__name__)


def _needs_patch() -> bool:
    """Return True if the stdlib sqlite3 lacks extension loading."""
    try:
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        conn.close()
        return False
    except AttributeError:
        return True


if _needs_patch():
    try:
        import pysqlite3

        sys.modules["sqlite3"] = pysqlite3
        sys.modules["sqlite3.dbapi2"] = pysqlite3.dbapi2
        logger.debug(
            "Patched sqlite3 with pysqlite3 (SQLite %s) for extension loading support",
            pysqlite3.sqlite_version,
        )
    except ImportError:
        logger.debug("pysqlite3-binary not installed; sqlite3 extension loading may be unavailable")
