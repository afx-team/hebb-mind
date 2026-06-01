"""Packaging configuration tests."""

from __future__ import annotations

from pathlib import Path


def test_static_assets_are_declared_as_package_data() -> None:
    pyproject = Path("pyproject.toml").read_text()
    assert "[tool.setuptools.package-data]" in pyproject
    assert "static/**/*" in pyproject
