"""Tests for the local embedding provider's shared ML-stack presence check."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable

import pytest

from hebb.embedding.local import is_ml_stack_present


def _stub_find_spec(present: set[str]) -> Callable[[str], object | None]:
    """Return a ``find_spec`` replacement resolving only ``present`` packages."""

    def _find_spec(name: str) -> object | None:
        return object() if name in present else None

    return _find_spec


def test_is_ml_stack_present_true_when_both_packages_importable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        importlib.util, "find_spec", _stub_find_spec({"sentence_transformers", "torch"})
    )
    assert is_ml_stack_present() is True


@pytest.mark.parametrize(
    "present",
    [
        # Finding #2: doctor used to check only sentence-transformers, so a
        # half-installed stack (st present, torch later removed) wrongly reported
        # "✓ importable". The shared check must require BOTH packages.
        {"sentence_transformers"},
        {"torch"},
        set(),
    ],
)
def test_is_ml_stack_present_false_unless_both_packages_importable(
    monkeypatch: pytest.MonkeyPatch, present: set[str]
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", _stub_find_spec(present))
    assert is_ml_stack_present() is False
