"""Tests for hebb.upgrade.helper — state transitions via the dry-run path.

The dry-run path exercises the full state machine (in_progress → success /
failed) without stopping a service or running a real package install.
"""

from __future__ import annotations

from pathlib import Path

from hebb.upgrade import helper
from hebb.upgrade import state as upgrade_state


def _seed(home: Path) -> None:
    upgrade_state.save(
        home,
        upgrade_state.UpgradeState(
            current_version="0.1.0",
            latest_version="0.2.0",
            available=True,
        ),
    )


def test_dry_run_success(tmp_path: Path) -> None:
    _seed(tmp_path)
    rc = helper.run_upgrade(
        home_dir=tmp_path, method="pip", parent_pid=0, grace=0.1, port=8321, dry_run=True
    )
    assert rc == 0
    st = upgrade_state.load(tmp_path)
    assert st.upgrade_in_progress is False
    assert st.last_upgrade is not None
    assert st.last_upgrade.status == "success"
    assert st.last_upgrade.method == "pip"
    assert st.last_upgrade.from_version == "0.1.0"
    assert st.last_upgrade.to_version == "0.2.0"
    # current bumped to target; nothing newer remains available.
    assert st.current_version == "0.2.0"
    assert st.available is False


def test_refuses_editable(tmp_path: Path) -> None:
    _seed(tmp_path)
    rc = helper.run_upgrade(
        home_dir=tmp_path, method="editable", parent_pid=0, grace=0.1, port=8321, dry_run=True
    )
    assert rc == 1
    st = upgrade_state.load(tmp_path)
    assert st.upgrade_in_progress is False
    assert st.last_upgrade is not None
    assert st.last_upgrade.status == "failed"
    # An editable refusal must not pretend the version moved.
    assert st.current_version == "0.1.0"


def test_main_parses_args(tmp_path: Path) -> None:
    _seed(tmp_path)
    rc = helper.main(
        ["--method", "pip", "--home", str(tmp_path), "--port", "8321", "--dry-run", "--grace", "0.1"]
    )
    assert rc == 0
    assert upgrade_state.load(tmp_path).last_upgrade.status == "success"  # type: ignore[union-attr]


def test_terminate_parent_no_sigkill_on_windows(monkeypatch) -> None:
    # On Windows signal.SIGKILL does not exist — _terminate_parent must never
    # reference it (it would AttributeError before the daemon is even stopped).
    sent: list[int] = []
    alive = {"v": True}
    monkeypatch.setattr(helper.os, "name", "nt")
    monkeypatch.setattr(helper.time, "sleep", lambda _s: None)
    monkeypatch.setattr(helper, "_pid_alive", lambda _pid: alive["v"])

    def fake_kill(_pid: int, sig: int) -> None:
        sent.append(sig)
        alive["v"] = False

    monkeypatch.setattr(helper.os, "kill", fake_kill)
    helper._terminate_parent(4321, grace=0.0)
    assert helper.signal.SIGTERM in sent
    assert helper.signal.SIGKILL not in sent


def test_spawn_detached_builds_expected_argv(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeProc:
        pid = 24680

    def fake_popen(argv, **kwargs):  # noqa: ANN001, ANN003
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(helper.subprocess, "Popen", fake_popen)
    pid = helper.spawn_detached(
        home_dir=tmp_path, port=8321, grace=30, method="pip", parent_pid=4321
    )
    assert pid == 24680
    argv = captured["argv"]
    assert "hebb.upgrade.helper" in argv
    assert "--method" in argv and "pip" in argv
    assert "--parent-pid" in argv and "4321" in argv
