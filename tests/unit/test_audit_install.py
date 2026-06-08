"""Audit lane H-config-install-service regression tests.

Covers:
  * C4 — service install pins an absolute, cwd-independent HEBB_HOME into the
    launchd plist / systemd unit / Windows wrapper (not the installer's cwd).
  * install F4 — systemd ExecStart shlex-quotes tokens with spaces.
  * install F5/F9 — plist / task XML escape XML metacharacters.
  * startup F2 — macOS stop uses launchctl bootout (not a no-op SIGTERM).
  * startup F10 — reinstall against a different home raises HomeConflictError
    unless --force.
  * install F8 — setup does not persist embedding config when verify fails.
  * llm F5 — loader update_config_field writes atomically (temp + os.replace).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hebb.config import loader
from hebb.utils import service_manager as sm

# ---------------------------------------------------------------------------
# C4 — HEBB_HOME is pinned, absolute, and cwd-independent
# ---------------------------------------------------------------------------


def test_resolve_service_home_explicit_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEBB_HOME", str(tmp_path / "env"))
    explicit = tmp_path / "explicit"
    assert sm.resolve_service_home(str(explicit)) == explicit.resolve()


def test_resolve_service_home_env_over_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEBB_HOME", str(tmp_path / "env"))
    assert sm.resolve_service_home(None) == (tmp_path / "env").resolve()


def test_resolve_service_home_default_is_dot_hebb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HEBB_HOME", raising=False)
    assert sm.resolve_service_home(None) == (Path.home() / ".hebb").resolve()


def test_launchd_plist_pins_hebb_home_independent_of_cwd(tmp_path: Path) -> None:
    home = tmp_path / "stable-home"
    mgr = sm.LaunchdManager(scope="user", home=home)
    plist = mgr._plist()
    assert "<key>HEBB_HOME</key>" in plist
    assert f"<string>{home}</string>" in plist
    # WorkingDirectory is the same stable home, not a cwd-derived workspace.
    assert plist.count(f"<string>{home}</string>") >= 2


def test_systemd_unit_pins_hebb_home(tmp_path: Path) -> None:
    home = tmp_path / "stable-home"
    mgr = sm.SystemdManager(scope="user", home=home)
    unit = mgr._unit()
    assert f"Environment=HEBB_HOME={home}" in unit
    assert f"WorkingDirectory={home}" in unit


def test_windows_wrapper_pins_hebb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    home = tmp_path / "stable-home"
    mgr = sm.WindowsTaskManager(scope="user", home=home)
    wrapper = mgr._wrapper_script()
    text = wrapper.read_text()
    assert f'set "HEBB_HOME={home}"' in text
    assert f'cd /d "{home}"' in text


# ---------------------------------------------------------------------------
# install F4 — systemd ExecStart handles spaces
# ---------------------------------------------------------------------------


def test_systemd_execstart_quotes_spaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spaced = "/Applications/My Tools/bin/hebb"
    monkeypatch.setattr(sm, "hebb_command", lambda: [spaced])
    mgr = sm.SystemdManager(scope="user", home=tmp_path)
    unit = mgr._unit()
    execstart = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
    # The spaced path must be quoted so systemd does not word-split it.
    assert "'/Applications/My Tools/bin/hebb'" in execstart


# ---------------------------------------------------------------------------
# install F5/F9 — XML metacharacters are escaped
# ---------------------------------------------------------------------------


def test_launchd_plist_escapes_xml_metachars(tmp_path: Path) -> None:
    home = tmp_path / "a&b<c>d"
    mgr = sm.LaunchdManager(scope="user", home=home)
    plist = mgr._plist()
    # Raw metacharacters must not appear inside the home value.
    assert "a&amp;b&lt;c&gt;d" in plist
    assert "<string>" + str(home) + "</string>" not in plist


def test_launchd_plist_escapes_program_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sm, "hebb_command", lambda: ["/bin/hebb & rm -rf"])
    mgr = sm.LaunchdManager(scope="user", home=tmp_path)
    plist = mgr._plist()
    assert "/bin/hebb &amp; rm -rf" in plist


def test_windows_task_xml_escapes_metachars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    home = tmp_path / "x&y"
    mgr = sm.WindowsTaskManager(scope="user", home=home)
    xml = mgr._task_xml()
    assert "x&amp;y" in xml


# ---------------------------------------------------------------------------
# startup F2 — macOS stop uses bootout, not SIGTERM
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="launchd is macOS-only")
def test_launchd_stop_uses_bootout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_launchctl(args: list[str], scope: sm.Scope) -> object:
        calls.append(args)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(sm, "_launchctl", fake_launchctl)
    mgr = sm.LaunchdManager(scope="user")
    # Pretend the plist exists so stop() proceeds.
    monkeypatch.setattr(type(mgr), "install_path", property(lambda self: tmp_path / "x.plist"))
    (tmp_path / "x.plist").write_text("<plist/>")
    mgr.stop()
    assert any("bootout" in a for a in calls)
    assert not any("kill" in a for a in calls)


def test_launchd_keepalive_is_conditional(tmp_path: Path) -> None:
    mgr = sm.LaunchdManager(scope="user", home=tmp_path)
    plist = mgr._plist()
    # KeepAlive must NOT be an unconditional <true/>, so a manual stop stays down.
    assert "<key>KeepAlive</key>\n  <true/>" not in plist
    assert "<key>SuccessfulExit</key>" in plist


# ---------------------------------------------------------------------------
# startup F10 — reinstall against a different home requires --force
# ---------------------------------------------------------------------------


def test_launchd_reinstall_different_home_conflicts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plist_path = tmp_path / "com.hebb.server.plist"
    old_home = tmp_path / "old-home"
    new_home = tmp_path / "new-home"

    # Write a plist already pointing at old_home.
    old_mgr = sm.LaunchdManager(scope="user", home=old_home)
    monkeypatch.setattr(type(old_mgr), "install_path", property(lambda self: plist_path))
    plist_path.write_text(old_mgr._plist())

    new_mgr = sm.LaunchdManager(scope="user", home=new_home)
    monkeypatch.setattr(type(new_mgr), "install_path", property(lambda self: plist_path))

    with pytest.raises(sm.HomeConflictError) as excinfo:
        new_mgr.install(force=False)
    assert str(old_home.resolve()) in str(excinfo.value) or str(old_home) in str(excinfo.value)


def test_registered_home_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plist_path = tmp_path / "com.hebb.server.plist"
    home = tmp_path / "home"
    mgr = sm.LaunchdManager(scope="user", home=home)
    monkeypatch.setattr(type(mgr), "install_path", property(lambda self: plist_path))
    plist_path.write_text(mgr._plist())
    assert mgr._registered_home() == str(home)


def test_systemd_registered_home_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    mgr = sm.SystemdManager(scope="user", home=home)
    unit_path = tmp_path / "hebb.service"
    unit_path.write_text(mgr._unit())
    monkeypatch.setattr(type(mgr), "install_path", property(lambda self: unit_path))
    assert mgr._registered_home() == str(home)


# ---------------------------------------------------------------------------
# llm F5 — loader update_config_field is atomic
# ---------------------------------------------------------------------------


def _write_config(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def test_update_config_field_atomic_and_no_temp_left(tmp_path: Path) -> None:
    cfg = tmp_path / "hebb.json"
    _write_config(cfg, {"embedding_dim": 384})

    path, validated = loader.update_config_field("embedding_dim", "768", cfg)
    assert path == cfg
    assert validated == 768
    assert json.loads(cfg.read_text())["embedding_dim"] == 768

    # No leftover temp / lock files clutter the directory beyond the lock sentinel.
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_atomic_write_uses_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "hebb.json"
    _write_config(cfg, {"embedding_dim": 384})

    seen: dict[str, object] = {}
    real_replace = loader.os.replace

    def spy_replace(src: str, dst: str) -> None:
        seen["src"] = src
        seen["dst"] = dst
        real_replace(src, dst)

    monkeypatch.setattr(loader.os, "replace", spy_replace)
    loader.update_config_field("embedding_dim", "512", cfg)
    # The destination is the real config and the source is a temp in the same dir.
    assert seen["dst"] == cfg
    assert str(seen["src"]).startswith(str(tmp_path))
    assert str(seen["src"]) != str(cfg)


def test_atomic_write_failure_leaves_original_intact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "hebb.json"
    _write_config(cfg, {"embedding_dim": 384})

    def boom(src: str, dst: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(loader.os, "replace", boom)
    with pytest.raises(OSError):
        loader.update_config_field("embedding_dim", "999", cfg)

    # Original file is untouched, no truncation.
    assert json.loads(cfg.read_text())["embedding_dim"] == 384
    # The temp file was cleaned up on failure.
    assert [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


# ---------------------------------------------------------------------------
# install F8 — setup persists embedding config only after verify succeeds
# ---------------------------------------------------------------------------


def test_setup_does_not_persist_embedding_on_verify_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import click
    from click.testing import CliRunner

    from hebb.cli.commands import setup as setup_mod

    cfg = tmp_path / "hebb.json"
    # Prior, working config the failed run must not corrupt.
    _write_config(cfg, {"embedding_provider": "local", "embedding_model": "good-model", "embedding_dim": 384})

    monkeypatch.setattr(setup_mod, "_ensure_initialized", lambda: cfg)

    class FakeSpec:
        model_id = "new-model"
        dimension = 768

    class FakeLang:
        language = "en"

    class FakeRegion:
        hf_endpoint = None
        region = "global"
        message = ""

    monkeypatch.setattr(setup_mod, "choose_model", lambda *a, **k: FakeSpec())
    monkeypatch.setattr(setup_mod, "resolve_language", lambda *a, **k: FakeLang())
    monkeypatch.setattr(setup_mod, "resolve_region", lambda *a, **k: FakeRegion())
    # Make selection trigger by forcing a non-legacy current model + explicit profile path.
    monkeypatch.setattr(setup_mod, "_should_select_model", lambda *a, **k: True)
    # prefetch succeeds, verify fails.
    monkeypatch.setattr(setup_mod, "prefetch_model", lambda *a, **k: tmp_path / "model")

    def boom_verify(*a: object, **k: object) -> int:
        raise RuntimeError("download corrupt")

    monkeypatch.setattr(setup_mod, "_verify_model", boom_verify)

    runner = CliRunner()
    result = runner.invoke(setup_mod.setup_cmd, [], catch_exceptions=False)
    assert result.exit_code != 0
    assert isinstance(result.exception, (click.ClickException, SystemExit)) or result.exit_code != 0

    # The prior working embedding config must be untouched — no half-applied model.
    persisted = json.loads(cfg.read_text())
    assert persisted["embedding_model"] == "good-model"
    assert persisted["embedding_dim"] == 384
