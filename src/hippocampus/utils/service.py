"""Shared service discovery and auto-start utilities.

Used by both the MCP server and Claude Code hooks to locate and
ensure the Hippocampus REST service is running.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time

import httpx

logger = logging.getLogger(__name__)


def resolve_base_url() -> str:
    """Resolve the running Hippocampus server URL.

    Resolution order:
      1. hippocampus.json config file (found by walking up from cwd)
      2. Default: http://localhost:8321
      3. HIPPOCAMPUS_URL env var overrides both (for remote services)
    """
    try:
        from hippocampus.config.loader import load_settings

        s = load_settings()
        host = "127.0.0.1" if s.host in ("0.0.0.0", "") else s.host
        base = f"http://{host}:{s.port}"
    except Exception:
        base = "http://localhost:8321"

    url = os.environ.get("HIPPOCAMPUS_URL")
    if url:
        return url.rstrip("/")

    return base


def is_server_running(url: str | None = None) -> bool:
    """Check if the Hippocampus service is reachable."""
    if url is None:
        url = resolve_base_url()
    try:
        httpx.get(f"{url}/health", timeout=3)
        return True
    except (httpx.ConnectError, httpx.RemoteProtocolError):
        return False


def ensure_service_running() -> None:
    """Auto-start the Hippocampus service if not already running."""
    url = resolve_base_url()

    if is_server_running(url):
        return

    # Skip auto-start if using a remote URL (user manages that server)
    if os.environ.get("HIPPOCAMPUS_URL"):
        return

    cmd = [sys.executable, "-m", "hippocampus.cli.main", "start", "-d"]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        try:
            subprocess.Popen(
                ["hippocampus", "start", "-d"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            return

    for _ in range(30):
        time.sleep(0.5)
        if is_server_running(url):
            return
