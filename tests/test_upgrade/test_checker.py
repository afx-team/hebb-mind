"""Tests for hebb.upgrade.checker — PyPI fetch + version compare.

No live PyPI requests in CI. We patch ``fetch_latest_version`` for the
``run_check`` integration tests and exercise the internal parsing helpers
directly for the pure-logic cases.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from hebb.upgrade import checker, state as upgrade_state


def test_parse_stable_versions_excludes_prereleases() -> None:
    releases = {
        "0.1.0": [],
        "0.1.1": [],
        "0.1.2rc1": [],
        "0.1.2.dev0": [],
        "0.1.2": [],
        "0.2.0a1": [],
    }
    parsed = checker._parse_stable_versions(releases)
    assert (0, 1, 0) in parsed
    assert (0, 1, 1) in parsed
    assert (0, 1, 2) in parsed
    assert len(parsed) == 3  # rc/dev/alpha all filtered out
    assert max(parsed) == (0, 1, 2)


def test_version_tuple_filters_prereleases() -> None:
    assert checker._version_tuple("0.1.3") == (0, 1, 3)
    assert checker._version_tuple("0.1.3rc1") is None
    assert checker._version_tuple("not-a-version") is None
    assert checker._version_tuple("0.1") is None


def test_index_base_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HEBB_PYPI_INDEX_URL", raising=False)
    assert checker._index_base_url() == "https://pypi.org"


def test_index_base_url_honors_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEBB_PYPI_INDEX_URL", "https://mirror.example.com/simple/")
    # Trailing /simple is stripped so /pypi/<name>/json works on devpi-style mirrors.
    assert checker._index_base_url() == "https://mirror.example.com"


@pytest.mark.asyncio
async def test_run_check_marks_available_when_newer(tmp_path: Path) -> None:
    with (
        patch("hebb.upgrade.checker.__version__", "0.1.3"),
        patch("hebb.upgrade.checker.fetch_latest_version", new=AsyncMock(return_value="0.1.4")),
    ):
        state = await checker.run_check(tmp_path)
    assert state.current_version == "0.1.3"
    assert state.latest_version == "0.1.4"
    assert state.available is True
    assert state.last_check_error is None
    # Persisted to disk
    reloaded = upgrade_state.load(tmp_path)
    assert reloaded.available is True


@pytest.mark.asyncio
async def test_run_check_marks_unavailable_when_same(tmp_path: Path) -> None:
    with (
        patch("hebb.upgrade.checker.__version__", "0.1.4"),
        patch("hebb.upgrade.checker.fetch_latest_version", new=AsyncMock(return_value="0.1.4")),
    ):
        state = await checker.run_check(tmp_path)
    assert state.available is False
    assert state.latest_version == "0.1.4"


@pytest.mark.asyncio
async def test_run_check_records_network_error(tmp_path: Path) -> None:
    with (
        patch("hebb.upgrade.checker.__version__", "0.1.3"),
        patch(
            "hebb.upgrade.checker.fetch_latest_version",
            new=AsyncMock(side_effect=RuntimeError("DNS failure")),
        ),
    ):
        state = await checker.run_check(tmp_path)
    assert state.last_check_error is not None
    assert "DNS failure" in state.last_check_error
    # We don't clobber latest_version on transient errors
    assert state.latest_version is None  # was never set


@pytest.mark.asyncio
async def test_run_check_resets_notified_flag_when_newer_appears(tmp_path: Path) -> None:
    # Seed state as if 0.1.4 was already notified.
    upgrade_state.save(
        tmp_path,
        upgrade_state.UpgradeState(
            current_version="0.1.3",
            latest_version="0.1.4",
            notified_for_version="0.1.4",
            available=True,
        ),
    )
    with (
        patch("hebb.upgrade.checker.__version__", "0.1.3"),
        patch("hebb.upgrade.checker.fetch_latest_version", new=AsyncMock(return_value="0.1.5")),
    ):
        state = await checker.run_check(tmp_path)
    # Newer version appeared → previous notification gets a fresh opportunity.
    assert state.notified_for_version is None
    assert state.latest_version == "0.1.5"


@pytest.mark.asyncio
async def test_run_check_resets_dismissal_when_newer_appears(tmp_path: Path) -> None:
    upgrade_state.save(
        tmp_path,
        upgrade_state.UpgradeState(
            current_version="0.1.3",
            latest_version="0.1.4",
            dismissed_for_version="0.1.4",
            available=True,
        ),
    )
    with (
        patch("hebb.upgrade.checker.__version__", "0.1.3"),
        patch("hebb.upgrade.checker.fetch_latest_version", new=AsyncMock(return_value="0.1.5")),
    ):
        state = await checker.run_check(tmp_path)
    assert state.dismissed_for_version is None
