"""Tests for stdio protection utilities."""

from __future__ import annotations

import os
import sys

import pytest

from hebb.utils.stdio_guard import (
    capture_stdout,
    restore_stdout,
    suppress_stdout_stderr,
)

# fd-level redirection (os.dup2 on fd 1) is POSIX-only; skip on Windows.
pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX fd redirection")


class TestCaptureRestore:
    def test_capture_redirects_to_stderr(self):
        """After capture, sys.stdout should be sys.stderr."""
        # Save original state
        try:
            capture_stdout()
            assert sys.stdout is sys.stderr
        finally:
            restore_stdout()
            # Verify we're back
            assert sys.stdout is not sys.stderr

    def test_restore_reverts(self):
        """After capture+restore, fd 1 is real stdout again."""
        # Write a marker to a pipe via fd 1 before/after
        r, w = os.pipe()
        orig_fd1 = os.dup(1)
        try:
            capture_stdout()
            restore_stdout()

            # Now redirect fd 1 to our pipe to test it works
            os.dup2(w, 1)
            os.write(1, b"hello")
            os.dup2(orig_fd1, 1)

            data = os.read(r, 100)
            assert data == b"hello"
        finally:
            os.close(r)
            os.close(w)
            os.close(orig_fd1)

    def test_restore_without_capture_is_noop(self):
        """Calling restore without capture should not crash."""
        restore_stdout()  # should be a no-op

    def test_python_level_redirect(self):
        """sys.stdout should point to stderr during capture."""
        orig = sys.stdout
        try:
            capture_stdout()
            assert sys.stdout is sys.stderr
            assert sys.stdout is not orig
        finally:
            restore_stdout()


class TestSuppressContextManager:
    def test_suppress_silences_output(self):
        """Within suppress, writes to fd 1 and 2 go to /dev/null."""
        r, w = os.pipe()
        orig_fd1 = os.dup(1)
        try:
            # Redirect fd 1 to pipe
            os.dup2(w, 1)

            with suppress_stdout_stderr():
                os.write(1, b"noise")  # should go to /dev/null

            # Write after context — should go to pipe
            os.write(1, b"signal")
            os.dup2(orig_fd1, 1)
            os.close(w)

            data = os.read(r, 100)
            assert data == b"signal"  # "noise" was suppressed
        finally:
            os.close(r)
            os.close(orig_fd1)

    def test_suppress_restores_on_exception(self):
        """fd 1 and 2 are restored even if the block raises."""
        r, w = os.pipe()
        orig_fd1 = os.dup(1)
        try:
            os.dup2(w, 1)

            try:
                with suppress_stdout_stderr():
                    raise ValueError("test")
            except ValueError:
                pass

            os.write(1, b"after")
            os.dup2(orig_fd1, 1)
            os.close(w)

            data = os.read(r, 100)
            assert data == b"after"
        finally:
            os.close(r)
            os.close(orig_fd1)
