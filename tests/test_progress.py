"""Tests for the tqdm progress-callback subclass."""

from __future__ import annotations

from hebb.embedding.progress import make_progress_tqdm


def test_update_invokes_callback_with_cumulative_bytes() -> None:
    events: list[tuple[int, int, str]] = []

    Cls = make_progress_tqdm(lambda d, t, desc: events.append((d, t, desc)))
    with Cls(total=100, desc="weights.bin") as bar:
        bar.update(25)
        bar.update(25)
        bar.update(50)

    # Three update() calls plus a close() event → at least four samples, ending at 100/100.
    assert events, "callback never fired"
    assert events[-1][0] == 100
    assert events[-1][1] == 100
    assert events[-1][2] == "weights.bin"


def test_callback_exception_does_not_break_download() -> None:
    def bad_cb(_d: int, _t: int, _desc: str) -> None:
        raise RuntimeError("intentional")

    Cls = make_progress_tqdm(bad_cb)
    # Whole loop must complete despite the callback exploding on every tick.
    with Cls(total=10, desc="x") as bar:
        for _ in range(5):
            bar.update(2)


def test_close_emits_final_event() -> None:
    events: list[tuple[int, int, str]] = []
    Cls = make_progress_tqdm(lambda d, t, desc: events.append((d, t, desc)))

    bar = Cls(total=4, desc="final")
    bar.update(4)
    bar.close()

    assert events[-1] == (4, 4, "final")
