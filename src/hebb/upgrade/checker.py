"""PyPI version check — async fetch + compare against the running ``__version__``.

Skips pre-releases (anything not matching ``MAJOR.MINOR.PATCH``). On network
failure, writes the error to ``last_check_error`` and leaves
``latest_version`` untouched so a transient outage doesn't clear a previously
known new version.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from hebb import __version__
from hebb.upgrade import state as upgrade_state
from hebb.upgrade.state import UpgradeState

logger = logging.getLogger(__name__)

PACKAGE_NAME = "hebb-mind"
DEFAULT_PYPI_BASE = "https://pypi.org"
REQUEST_TIMEOUT_SECONDS = 10.0

_STABLE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _index_base_url() -> str:
    """Return the PyPI base URL, honoring ``HEBB_PYPI_INDEX_URL`` override.

    The override may be a full base URL (``https://mirror/`` or
    ``https://mirror/simple``). We strip any trailing ``/simple`` so the
    ``/pypi/<name>/json`` endpoint works on devpi-style mirrors.
    """
    base = os.environ.get("HEBB_PYPI_INDEX_URL") or DEFAULT_PYPI_BASE
    base = base.rstrip("/")
    if base.endswith("/simple"):
        base = base[: -len("/simple")]
    return base


def _parse_stable_versions(releases: dict[str, object]) -> list[tuple[int, int, int]]:
    """Filter to stable releases and parse as ``(major, minor, patch)`` tuples."""
    out: list[tuple[int, int, int]] = []
    for v in releases.keys():
        if _STABLE_VERSION_RE.match(v):
            parts = v.split(".")
            out.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return out


def _version_tuple(v: str) -> tuple[int, int, int] | None:
    if not _STABLE_VERSION_RE.match(v):
        return None
    a, b, c = v.split(".")
    return (int(a), int(b), int(c))


def _format_version(t: tuple[int, int, int]) -> str:
    return f"{t[0]}.{t[1]}.{t[2]}"


async def fetch_latest_version(client: httpx.AsyncClient | None = None) -> str:
    """Fetch the latest stable version from PyPI.

    Raises:
        httpx.HTTPError: on network or HTTP error.
        ValueError: if the response has no parseable stable version.
    """
    url = f"{_index_base_url()}/pypi/{PACKAGE_NAME}/json"
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    assert client is not None
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if own_client:
            await client.aclose()

    # info.version is PyPI's reported latest; fall back to scanning releases.
    info_version = payload.get("info", {}).get("version")
    if isinstance(info_version, str) and _STABLE_VERSION_RE.match(info_version):
        return info_version

    releases = payload.get("releases", {})
    if not isinstance(releases, dict):
        raise ValueError("PyPI JSON has no 'releases' field")
    stable = _parse_stable_versions(releases)
    if not stable:
        raise ValueError("No stable releases found on PyPI")
    return _format_version(max(stable))


async def run_check(home_dir: Path, client: httpx.AsyncClient | None = None) -> UpgradeState:
    """Perform a PyPI check and persist the updated state. Always returns the new state.

    Network errors are caught and recorded in ``last_check_error``. The
    ``latest_version`` field is preserved on error so callers can still display
    a previously-detected new version.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    state = upgrade_state.load(home_dir)
    state.current_version = __version__

    try:
        latest = await fetch_latest_version(client=client)
    except Exception as exc:
        logger.warning("Upgrade check failed: %s", exc)
        state.checked_at = now_iso
        state.last_check_error = f"{type(exc).__name__}: {exc}"
        upgrade_state.save(home_dir, state)
        return state

    current_t = _version_tuple(__version__)
    latest_t = _version_tuple(latest)
    available = bool(current_t and latest_t and latest_t > current_t)

    state.checked_at = now_iso
    state.last_check_error = None
    state.latest_version = latest
    state.available = available

    # Reset notification flag when a newer version supersedes the previously notified one
    if state.notified_for_version and latest_t and _version_tuple(state.notified_for_version):
        prev_t = _version_tuple(state.notified_for_version)
        if prev_t and latest_t > prev_t:
            state.notified_for_version = None
    # Same logic for "dismissed for version": if a newer version appears, un-dismiss
    if state.dismissed_for_version and latest_t and _version_tuple(state.dismissed_for_version):
        prev_t = _version_tuple(state.dismissed_for_version)
        if prev_t and latest_t > prev_t:
            state.dismissed_for_version = None

    upgrade_state.save(home_dir, state)
    logger.info(
        "Upgrade check: current=%s latest=%s available=%s",
        __version__,
        latest,
        available,
    )
    return state
