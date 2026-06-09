"""Tests for the platform service manager and the `hebb service` CLI."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from hebb.cli.commands import service as service_cli
from hebb.cli.commands import status as status_cli
from hebb.utils import service_manager
from hebb.utils.service_manager import (
    LaunchdManager,
    ServiceError,
    ServiceNotInstalledError,
    SystemdManager,
    WindowsTaskManager,
    get_manager,
)


def _completed(args: list[str], returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("system", "scope", "expected_cls"),
    [
        ("Darwin", "user", LaunchdManager),
        ("Linux", "user", SystemdManager),
        ("Linux", "system", SystemdManager),
        ("Windows", "user", WindowsTaskManager),
    ],
)
def test_get_manager_picks_platform_backend(monkeypatch: pytest.MonkeyPatch, system: str, scope: str, expected_cls: type) -> None:
    monkeypatch.setattr(service_manager.platform, "system", lambda: system)
    manager = get_manager(scope=scope)  # type: ignore[arg-type]
    assert isinstance(manager, expected_cls)
    assert manager.scope == scope


def test_get_manager_unsupported_platform_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_manager.platform, "system", lambda: "FreeBSD")
    with pytest.raises(service_manager.UnsupportedPlatformError):
        get_manager()


# ---------------------------------------------------------------------------
# launchd (macOS)
# ---------------------------------------------------------------------------


def test_launchd_install_writes_plist_and_bootstraps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plist_path = tmp_path / "com.hebb.server.plist"
    monkeypatch.setattr(service_manager, "_launchd_path", lambda scope: plist_path)
    monkeypatch.setattr(service_manager, "_launchd_domain", lambda scope: "gui/501")
    monkeypatch.setattr(service_manager, "hebb_command", lambda: ["/usr/local/bin/hebb"])
    monkeypatch.setattr(service_manager, "workspace_dir", lambda: str(tmp_path))

    calls: list[list[str]] = []
    loaded = {"value": False}

    def fake_launchctl(args: list[str], scope: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[0] == "bootout":
            loaded["value"] = False
            return _completed(args, 0)
        if args[0] == "bootstrap":
            loaded["value"] = True
            return _completed(args, 0)
        if args[0] == "print":
            return _completed(args, 0 if loaded["value"] else 1)
        return _completed(args, 0)

    monkeypatch.setattr(service_manager, "_launchctl", fake_launchctl)

    manager = LaunchdManager(scope="user")
    manager.install()

    assert plist_path.exists()
    assert "/usr/local/bin/hebb" in plist_path.read_text()
    assert "_serve" in plist_path.read_text()
    assert any(args[0] == "bootstrap" for args in calls)
    assert any(args[:2] == ["kickstart", "-k"] for args in calls)


def test_launchd_install_raises_when_bootstrap_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plist_path = tmp_path / "com.hebb.server.plist"
    monkeypatch.setattr(service_manager, "_launchd_path", lambda scope: plist_path)
    monkeypatch.setattr(service_manager, "_launchd_domain", lambda scope: "gui/501")
    monkeypatch.setattr(service_manager, "hebb_command", lambda: ["/usr/local/bin/hebb"])
    monkeypatch.setattr(service_manager, "workspace_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        service_manager,
        "_launchctl",
        lambda args, scope: _completed(args, 5, stderr="bootstrap denied"),
    )

    manager = LaunchdManager(scope="user")
    with pytest.raises(ServiceError):
        manager.install()


def test_launchd_uninstall_when_not_installed_is_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plist_path = tmp_path / "missing.plist"
    monkeypatch.setattr(service_manager, "_launchd_path", lambda scope: plist_path)
    monkeypatch.setattr(service_manager, "_launchctl", lambda args, scope: _completed(args, 0))

    LaunchdManager(scope="user").uninstall()  # should not raise


def test_launchd_start_without_install_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_manager, "_launchd_path", lambda scope: tmp_path / "missing.plist")
    with pytest.raises(ServiceNotInstalledError):
        LaunchdManager(scope="user").start()


# ---------------------------------------------------------------------------
# systemd (Linux)
# ---------------------------------------------------------------------------


def test_systemd_user_install_writes_unit_and_enables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(service_manager, "hebb_command", lambda: ["/usr/local/bin/hebb"])
    monkeypatch.setattr(service_manager, "workspace_dir", lambda: str(tmp_path))
    monkeypatch.setattr(service_manager.shutil, "which", lambda name: "/bin/systemctl" if name == "systemctl" else None)

    calls: list[list[str]] = []

    def fake_systemctl(scope: str, args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
        calls.append([scope, *args])
        return _completed(args, 0)

    monkeypatch.setattr(service_manager, "_systemctl", fake_systemctl)

    manager = SystemdManager(scope="user")
    manager.install()

    unit_path = manager.install_path
    assert unit_path.exists()
    text = unit_path.read_text()
    assert "ExecStart=/usr/local/bin/hebb _serve" in text
    assert "WantedBy=default.target" in text
    assert any(call[1:] == ["daemon-reload"] for call in calls)
    assert any(call[1:] == ["enable", "hebb"] for call in calls)
    assert any(call[1:] == ["start", "hebb"] for call in calls)


def test_systemd_system_unit_includes_user_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_manager, "hebb_command", lambda: ["/usr/local/bin/hebb"])
    monkeypatch.setattr(service_manager, "workspace_dir", lambda: str(tmp_path))
    monkeypatch.setenv("USER", "alice")

    manager = SystemdManager(scope="system")
    unit = manager._unit()
    assert "User=alice" in unit
    assert "WantedBy=multi-user.target" in unit


def test_systemd_status_reports_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    status = SystemdManager(scope="user").status()
    assert status.installed is False
    assert status.running is False


# ---------------------------------------------------------------------------
# Windows Task Scheduler
# ---------------------------------------------------------------------------


def test_windows_install_invokes_schtasks_with_xml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("USERDOMAIN", "WIN")
    monkeypatch.setenv("USERNAME", "alice")
    monkeypatch.setattr(service_manager, "hebb_command", lambda: ["C:\\Python\\hebb.exe"])
    monkeypatch.setattr(service_manager, "workspace_dir", lambda: str(tmp_path))
    monkeypatch.setattr(service_manager.shutil, "which", lambda name: "C:\\Windows\\System32\\schtasks.exe")

    calls: list[list[str]] = []

    def fake_schtasks(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[:1] == ["/Query"]:
            return _completed(args, 0)
        return _completed(args, 0)

    monkeypatch.setattr(service_manager, "_schtasks", fake_schtasks)

    manager = WindowsTaskManager(scope="user")
    manager.install()

    create_call = next(c for c in calls if c[:1] == ["/Create"])
    assert "/XML" in create_call
    xml_path = Path(create_call[create_call.index("/XML") + 1])
    xml_text = xml_path.read_text(encoding="utf-16")
    assert "HebbMind" in xml_text
    assert "LogonTrigger" in xml_text
    assert "RestartOnFailure" in xml_text
    assert "LeastPrivilege" in xml_text
    # Wrapper script must exist alongside the XML.
    wrapper = Path(os.environ["LOCALAPPDATA"]) / "HebbMind" / "hebb-serve.cmd"
    assert wrapper.exists()
    assert "_serve" in wrapper.read_text()


def test_windows_system_install_runs_as_system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData"))
    monkeypatch.setattr(service_manager, "hebb_command", lambda: ["C:\\hebb.exe"])
    monkeypatch.setattr(service_manager, "workspace_dir", lambda: str(tmp_path))
    monkeypatch.setattr(service_manager.shutil, "which", lambda name: "C:\\schtasks.exe")

    calls: list[list[str]] = []

    def fake_schtasks(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _completed(args, 0)

    monkeypatch.setattr(service_manager, "_schtasks", fake_schtasks)
    WindowsTaskManager(scope="system").install()

    create_call = next(c for c in calls if c[:1] == ["/Create"])
    assert create_call[-2:] == ["/RU", "SYSTEM"]


def test_windows_install_raises_when_schtasks_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_manager.shutil, "which", lambda name: None)
    with pytest.raises(ServiceError):
        WindowsTaskManager(scope="user").install()


# ---------------------------------------------------------------------------
# CLI command surface
# ---------------------------------------------------------------------------


class _FakeManager:
    display_name = "fake"
    install_path = None
    logs_hint = ""
    manage_hints: list[str] = []
    scope = "user"

    def __init__(self) -> None:
        self.installed = False
        self.events: list[str] = []

    def install(self, force: bool = False) -> None:
        self.installed = True
        self.events.append("install")

    def uninstall(self) -> None:
        self.installed = False
        self.events.append("uninstall")

    def start(self) -> None:
        if not self.installed:
            raise ServiceNotInstalledError()
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")

    def restart(self) -> None:
        self.events.append("restart")

    def status(self) -> service_manager.ServiceStatus:
        return service_manager.ServiceStatus(installed=self.installed, running=False, detail="fake")


def test_service_install_command_invokes_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeManager()
    monkeypatch.setattr(service_cli, "get_manager", lambda scope, home=None: fake)
    monkeypatch.setattr(service_cli, "_wait_until_healthy", lambda url, **_: True)
    # The venv guard prompts when tests run inside a virtualenv; bypass it here
    # so this test stays focused on the manager invocation path.
    monkeypatch.setattr(service_cli, "_warn_if_venv", lambda: None)

    runner = CliRunner()
    result = runner.invoke(service_cli.service_cmd, ["install"])
    assert result.exit_code == 0, result.output
    assert fake.events == ["install"]


def test_service_uninstall_command_skips_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeManager()
    monkeypatch.setattr(service_cli, "get_manager", lambda scope, home=None: fake)

    runner = CliRunner()
    result = runner.invoke(service_cli.service_cmd, ["uninstall"])
    assert result.exit_code == 0, result.output
    assert "not installed" in result.output


def test_service_start_command_complains_if_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeManager()
    monkeypatch.setattr(service_cli, "get_manager", lambda scope: fake)

    runner = CliRunner()
    result = runner.invoke(service_cli.service_cmd, ["start"])
    assert result.exit_code != 0
    assert "service install" in result.output


def test_top_level_status_reports_not_installed_when_server_down(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeManager()
    monkeypatch.setattr(status_cli, "get_manager", lambda: fake)
    monkeypatch.setattr(status_cli, "resolve_server_url", lambda: "http://127.0.0.1:9999")

    import httpx

    def _refuse(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(status_cli.httpx, "get", _refuse)

    runner = CliRunner()
    result = runner.invoke(status_cli.status_cmd, [])
    assert result.exit_code != 0
    assert "Installed:" in result.output
    assert "Cannot connect" in result.output
