"""Service discovery + on-demand start used by the MCP server and Claude Code hooks.

The supported lifecycle is OS-managed: launchd / systemd / Task Scheduler
own the process. These helpers locate the running server and, when it
isn't running, ask the *installed* service manager to start it. If no
service is installed, the user gets a clear instruction to run
``hebb service install`` — we no longer fork a daemon ourselves.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)


def resolve_base_url() -> str:
    """Resolve the running Hebb Mind server URL.

    Resolution order:
      1. ``HEBB_URL`` env var (for remote services)
      2. ``hebb.json`` config file (found by walking up from cwd)
      3. Default: ``http://localhost:8321``
    """
    url = os.environ.get("HEBB_URL")
    if url:
        return url.rstrip("/")

    try:
        from hebb.config.loader import load_settings

        s = load_settings()
        host = "127.0.0.1" if s.host in ("0.0.0.0", "") else s.host
        return f"http://{host}:{s.port}"
    except Exception:
        return "http://localhost:8321"


def is_server_running(url: str | None = None) -> bool:
    """Check if the Hebb Mind service is reachable."""
    if url is None:
        url = resolve_base_url()
    try:
        httpx.get(f"{url}/health", timeout=3)
        return True
    except (
        httpx.ConnectError,
        httpx.RemoteProtocolError,
        httpx.ReadError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
    ):
        return False


def ensure_service_running(*, wait_seconds: float = 15.0) -> bool:
    """Ask the OS service manager to start Hebb Mind if it isn't running.

    Returns ``True`` if the server is reachable after the attempt,
    ``False`` if no installed service was available or it failed to start.
    Never blocks the caller for more than *wait_seconds*.
    """
    url = resolve_base_url()

    if is_server_running(url):
        return True

    # Remote URL — the user manages that server.
    if os.environ.get("HEBB_URL"):
        return False

    try:
        from hebb.utils.service_manager import (
            ServiceError,
            ServiceNotInstalledError,
            UnsupportedPlatformError,
            get_manager,
        )

        manager = get_manager()
        try:
            manager.start()
        except ServiceNotInstalledError:
            logger.warning("Hebb Mind service is not installed. Run: hebb service install")
            return False
        except ServiceError as exc:
            logger.warning("Failed to start Hebb Mind service: %s", exc)
            return False
    except UnsupportedPlatformError as exc:
        logger.warning("%s", exc)
        return False
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Could not contact service manager: %s", exc)
        return False

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if is_server_running(url):
            return True
        time.sleep(0.5)
    return False
