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


def make_progress_tqdm(callback: ProgressCallback) -> type:
    """Return a tqdm subclass that calls ``callback`` on every update."""
    from tqdm import tqdm

    class ProgressTqdm(tqdm):  # type: ignore[misc]
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
