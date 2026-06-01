"""End-to-end smoke tests for the installed ``hebb`` CLI entrypoint.

These spawn the real console script (requires ``pip install -e .``) and assert
the process resolves and runs — the only layer that catches entrypoint /
packaging / PATH regressions that in-process ``CliRunner`` tests cannot see.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.e2e

HEBB = shutil.which("hebb")
_skip_no_cli = pytest.mark.skipif(HEBB is None, reason="`hebb` entrypoint not on PATH (package not installed)")


@_skip_no_cli
def test_cli_version() -> None:
    proc = subprocess.run([HEBB, "--version"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "hebb" in proc.stdout.lower()


@_skip_no_cli
def test_cli_help_lists_commands() -> None:
    proc = subprocess.run([HEBB, "--help"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "Usage" in proc.stdout or "Commands" in proc.stdout
