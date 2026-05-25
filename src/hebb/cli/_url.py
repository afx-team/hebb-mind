"""Shared URL helpers for CLI commands.

Used by ``hebb console`` / ``hebb status`` / ``hebb service`` to resolve
the Web Console / API URL from settings consistently.
"""

from __future__ import annotations

from hebb.config.loader import load_settings


def resolve_server_url() -> str:
    """Return ``http://<host>:<port>`` derived from the active settings.

    ``0.0.0.0`` and empty host are rewritten to ``127.0.0.1`` so the URL is
    usable from a browser or local healthcheck.
    """
    settings = load_settings()
    host = "127.0.0.1" if settings.host in ("0.0.0.0", "") else settings.host
    return f"http://{host}:{settings.port}"
