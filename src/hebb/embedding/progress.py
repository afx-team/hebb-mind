"""tqdm subclass that forwards model-download progress to a callback.

``huggingface_hub.snapshot_download`` accepts a ``tqdm_class`` keyword. By
substituting a subclass whose ``update`` hook calls back into our task table
(see ``hebb.server.downloads``), the web console can poll real byte counts
instead of staring at a static "Testing…" spinner.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[int, int, str], None]
"""Signature: (bytes_done, bytes_total, current_file_desc) -> None.

Callbacks must never raise — exceptions inside ``update`` would surface as
mid-download failures with confusing tracebacks. The factory below wraps every
invocation in a bare ``except`` to enforce that.
"""


class _SilentProgressOutput:
    """Discard tqdm rendering while preserving its internal counters."""

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None


_SILENT_PROGRESS_OUTPUT = _SilentProgressOutput()


def make_progress_tqdm(callback: ProgressCallback, *, silent: bool = False) -> type:
    """Return a tqdm subclass that calls ``callback`` on every update.

    Args:
        callback: Consumer of byte progress updates.
        silent: Suppress tqdm's own terminal rendering when another UI renders
            the callback events.

    Returns:
        A tqdm-compatible progress class.
    """
    from tqdm import tqdm  # type: ignore[import-untyped]

    class ProgressTqdm(tqdm):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            if silent:
                kwargs["file"] = _SILENT_PROGRESS_OUTPUT
            super().__init__(*args, **kwargs)

        def update(self, n: int | float = 1) -> bool | None:
            ret = super().update(n)
            try:
                callback(int(self.n or 0), int(self.total or 0), str(self.desc or ""))
            except Exception:
                pass
            return ret

        def close(self) -> Any:
            try:
                callback(int(self.n or 0), int(self.total or 0), str(self.desc or ""))
            except Exception:
                pass
            return super().close()

    return ProgressTqdm
