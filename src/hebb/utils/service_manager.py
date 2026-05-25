"""Platform-specific service managers for Hebb Mind background startup.

Hebb Mind always runs as an OS-managed background service. This module
abstracts launchd (macOS), systemd (Linux), and Task Scheduler (Windows)
behind a single :class:`ServiceManager` interface.

Permissions
-----------
Default scope is ``user`` — never requires admin/sudo:
  * macOS:   ``~/Library/LaunchAgents/com.hebb.server.plist`` (LaunchAgent)
  * Linux:   ``~/.config/systemd/user/hebb.service`` (systemd --user unit)
  * Windows: per-user Scheduled Task ``HebbMind`` (interactive logon trigger)

Scope ``system`` enables system-wide auto-start and requires elevation:
  * macOS:   ``/Library/LaunchDaemons/com.hebb.server.plist`` (root)
  * Linux:   ``/etc/systemd/system/hebb.service`` (sudo)
  * Windows: SYSTEM-account Scheduled Task (admin)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hebb.utils.cli_paths import hebb_command as _hebb_argv

Scope = Literal["user", "system"]

SERVICE_LABEL = "com.hebb.server"
SERVICE_NAME = "hebb"
WINDOWS_TASK_NAME = "HebbMind"


@dataclass(frozen=True)
class ServiceStatus:
    """Snapshot of an OS-level service registration."""

    installed: bool
    running: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hebb_command() -> list[str]:
    """Return the argv to invoke the hebb CLI as an absolute command.

    Delegates to :mod:`hebb.utils.cli_paths` so the same resolution logic
    drives launchd plists, systemd units, Task Scheduler XML, *and* the
    Claude Code / Codex integrations.
    """
    return _hebb_argv()


def workspace_dir() -> str:
    """Return the workspace root that services run in."""
    from hebb.config.workspace import resolve_workspace

    return str(resolve_workspace())


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class ServiceManager:
    """Abstract base — every platform implements install/uninstall/start/stop/status."""

    scope: Scope = "user"

    # Lifecycle ------------------------------------------------------------
    def install(self) -> None:
        raise NotImplementedError

    def uninstall(self) -> None:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def restart(self) -> None:
        self.stop()
        self.start()

    def status(self) -> ServiceStatus:
        raise NotImplementedError

    # Introspection --------------------------------------------------------
    @property
    def display_name(self) -> str:
        raise NotImplementedError

    @property
    def install_path(self) -> Path | None:
        """Disk artifact backing the service — plist / unit / task XML."""
        return None

    @property
    def logs_hint(self) -> str:
        """Human-readable hint for tailing logs."""
        return ""

    @property
    def manage_hints(self) -> list[str]:
        """Native commands the user can run after install."""
        return []


# ---------------------------------------------------------------------------
# macOS — launchd
# ---------------------------------------------------------------------------


def _launchd_path(scope: Scope) -> Path:
    if scope == "system":
        return Path("/Library/LaunchDaemons") / f"{SERVICE_LABEL}.plist"
    return Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"


def _launchd_domain(scope: Scope) -> str:
    if scope == "system":
        return "system"
    return f"gui/{os.getuid()}"


def _launchd_target(scope: Scope) -> str:
    return f"{_launchd_domain(scope)}/{SERVICE_LABEL}"


def _launchctl(args: list[str], scope: Scope) -> subprocess.CompletedProcess[str]:
    """Run ``launchctl`` — prefixed with ``sudo`` when targeting the system domain."""
    cmd = ["launchctl", *args]
    if scope == "system" and os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _write_with_sudo(path: Path, contents: str) -> None:
    """Write *contents* to *path*, escalating with sudo when needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    except PermissionError:
        subprocess.run(["sudo", "mkdir", "-p", str(path.parent)], check=True)
        subprocess.run(["sudo", "tee", str(path)], input=contents, text=True, check=True, stdout=subprocess.DEVNULL)


def _remove_with_sudo(path: Path) -> None:
    try:
        path.unlink()
    except PermissionError:
        subprocess.run(["sudo", "rm", str(path)], check=True)


class LaunchdManager(ServiceManager):
    """macOS launchd LaunchAgent (user) or LaunchDaemon (system)."""

    def __init__(self, scope: Scope = "user") -> None:
        self.scope = scope

    @property
    def display_name(self) -> str:
        return f"launchd ({self.scope})"

    @property
    def install_path(self) -> Path:
        return _launchd_path(self.scope)

    @property
    def logs_hint(self) -> str:
        return "tail -f /tmp/hebb.log /tmp/hebb.err"

    @property
    def manage_hints(self) -> list[str]:
        target = _launchd_target(self.scope)
        return [
            f"launchctl print {target}",
            f"launchctl kickstart -k {target}",
        ]

    def _plist(self) -> str:
        program_args = hebb_command() + ["_serve"]
        args_xml = "\n".join(f"    <string>{a}</string>" for a in program_args)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{SERVICE_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{args_xml}
  </array>
  <key>WorkingDirectory</key>
  <string>{workspace_dir()}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>/tmp/hebb.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/hebb.err</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
  </dict>
</dict>
</plist>
"""

    # Lifecycle ------------------------------------------------------------
    def install(self) -> None:
        path = self.install_path
        _write_with_sudo(path, self._plist())
        # Re-register so plist changes take effect, then start it.
        self._bootout()
        result = _launchctl(["bootstrap", _launchd_domain(self.scope), str(path)], self.scope)
        if result.returncode != 0:
            # Fall back to legacy load for older macOS.
            legacy = _launchctl(["load", str(path)], self.scope)
            if legacy.returncode != 0 and not self._is_loaded():
                raise ServiceError(
                    f"launchctl bootstrap failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
                )
        kickstart = _launchctl(["kickstart", "-k", _launchd_target(self.scope)], self.scope)
        if kickstart.returncode != 0 and not self._is_loaded():
            raise ServiceError(f"launchctl kickstart failed: {kickstart.stderr.strip()}")
        if not self._is_loaded():
            raise ServiceError("launchd did not register the Hebb Mind service.")

    def uninstall(self) -> None:
        if not self.install_path.exists():
            return
        self._bootout()
        _remove_with_sudo(self.install_path)

    def start(self) -> None:
        if not self.install_path.exists():
            raise ServiceNotInstalledError()
        result = _launchctl(["kickstart", _launchd_target(self.scope)], self.scope)
        if result.returncode != 0:
            raise ServiceError(f"launchctl kickstart failed: {result.stderr.strip()}")

    def stop(self) -> None:
        if not self.install_path.exists():
            return
        # ``kill`` sends a signal but keeps the service loaded so KeepAlive may relaunch.
        # We want a real stop — use ``bootout`` then ``bootstrap`` for a true stop+keep-installed cycle.
        _launchctl(["kill", "SIGTERM", _launchd_target(self.scope)], self.scope)

    def restart(self) -> None:
        if not self.install_path.exists():
            raise ServiceNotInstalledError()
        result = _launchctl(["kickstart", "-k", _launchd_target(self.scope)], self.scope)
        if result.returncode != 0:
            raise ServiceError(f"launchctl kickstart failed: {result.stderr.strip()}")

    def status(self) -> ServiceStatus:
        if not self.install_path.exists():
            return ServiceStatus(installed=False, running=False, detail="not installed")
        loaded = self._is_loaded()
        if not loaded:
            return ServiceStatus(installed=True, running=False, detail="installed, not loaded")
        # Parse `launchctl print` for PID — present means running.
        result = _launchctl(["print", _launchd_target(self.scope)], self.scope)
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("pid ="):
                return ServiceStatus(installed=True, running=True, detail=stripped)
        return ServiceStatus(installed=True, running=False, detail="loaded, idle")

    # Internals ------------------------------------------------------------
    def _is_loaded(self) -> bool:
        return _launchctl(["print", _launchd_target(self.scope)], self.scope).returncode == 0

    def _bootout(self) -> None:
        _launchctl(["bootout", _launchd_domain(self.scope), str(self.install_path)], self.scope)


# ---------------------------------------------------------------------------
# Linux — systemd
# ---------------------------------------------------------------------------


def _systemctl(scope: Scope, args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    cmd: list[str] = ["systemctl"]
    if scope == "user":
        cmd.append("--user")
    cmd.extend(args)
    if scope == "system" and os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


class SystemdManager(ServiceManager):
    """systemd user unit (no root) or system unit (requires sudo)."""

    def __init__(self, scope: Scope = "user") -> None:
        self.scope = scope

    @property
    def display_name(self) -> str:
        return f"systemd ({self.scope})"

    @property
    def install_path(self) -> Path:
        if self.scope == "system":
            return Path("/etc/systemd/system") / f"{SERVICE_NAME}.service"
        config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(config_home) / "systemd" / "user" / f"{SERVICE_NAME}.service"

    @property
    def logs_hint(self) -> str:
        if self.scope == "user":
            return f"journalctl --user -u {SERVICE_NAME} -f"
        return f"journalctl -u {SERVICE_NAME} -f"

    @property
    def manage_hints(self) -> list[str]:
        prefix = "systemctl --user" if self.scope == "user" else "sudo systemctl"
        hints = [
            f"{prefix} status {SERVICE_NAME}",
            f"{prefix} restart {SERVICE_NAME}",
        ]
        if self.scope == "user":
            hints.append("loginctl enable-linger $USER   # keep running across logout / at boot")
        return hints

    def _unit(self) -> str:
        cmd = " ".join(hebb_command() + ["_serve"])
        install_target = "default.target" if self.scope == "user" else "multi-user.target"
        # Optional User= field — only on system scope.
        user_line = f"User={os.environ.get('USER', SERVICE_NAME)}\n" if self.scope == "system" else ""
        return f"""[Unit]
Description=Hebb Mind Memory Server
After=network.target

[Service]
Type=simple
{user_line}WorkingDirectory={workspace_dir()}
ExecStart={cmd}
Restart=on-failure
RestartSec=5

[Install]
WantedBy={install_target}
"""

    # Lifecycle ------------------------------------------------------------
    def install(self) -> None:
        if not shutil.which("systemctl"):
            raise ServiceError("systemctl not found — is systemd installed and active?")
        _write_with_sudo(self.install_path, self._unit())
        _systemctl(self.scope, ["daemon-reload"], check=True)
        _systemctl(self.scope, ["enable", SERVICE_NAME], check=True)
        _systemctl(self.scope, ["start", SERVICE_NAME], check=True)

    def uninstall(self) -> None:
        if not self.install_path.exists():
            return
        _systemctl(self.scope, ["stop", SERVICE_NAME])
        _systemctl(self.scope, ["disable", SERVICE_NAME])
        _remove_with_sudo(self.install_path)
        _systemctl(self.scope, ["daemon-reload"])

    def start(self) -> None:
        if not self.install_path.exists():
            raise ServiceNotInstalledError()
        result = _systemctl(self.scope, ["start", SERVICE_NAME])
        if result.returncode != 0:
            raise ServiceError(f"systemctl start failed: {result.stderr.strip()}")

    def stop(self) -> None:
        if not self.install_path.exists():
            return
        _systemctl(self.scope, ["stop", SERVICE_NAME])

    def restart(self) -> None:
        if not self.install_path.exists():
            raise ServiceNotInstalledError()
        result = _systemctl(self.scope, ["restart", SERVICE_NAME])
        if result.returncode != 0:
            raise ServiceError(f"systemctl restart failed: {result.stderr.strip()}")

    def status(self) -> ServiceStatus:
        if not self.install_path.exists():
            return ServiceStatus(installed=False, running=False, detail="not installed")
        active = _systemctl(self.scope, ["is-active", SERVICE_NAME])
        running = active.stdout.strip() == "active"
        return ServiceStatus(installed=True, running=running, detail=active.stdout.strip())


# ---------------------------------------------------------------------------
# Windows — Task Scheduler
# ---------------------------------------------------------------------------


def _schtasks(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, check=False)


class WindowsTaskManager(ServiceManager):
    """Windows Scheduled Task with an at-logon trigger and restart-on-failure.

    User scope uses ``InteractiveToken`` + ``LeastPrivilege`` — no admin needed.
    System scope runs the task as ``SYSTEM`` and must be created from an
    elevated shell.
    """

    def __init__(self, scope: Scope = "user") -> None:
        self.scope = scope

    @property
    def display_name(self) -> str:
        return f"Task Scheduler ({self.scope})"

    @property
    def install_path(self) -> Path | None:
        # Task XML lives inside the Task Scheduler registry; no on-disk artifact.
        return None

    @property
    def logs_hint(self) -> str:
        # Windows Task Scheduler does not capture stdout/stderr by default;
        # _serve writes to %TEMP%\hebb.log via the wrapper script below.
        return r"%TEMP%\hebb.log"

    @property
    def manage_hints(self) -> list[str]:
        return [
            f'schtasks /Query /TN "{WINDOWS_TASK_NAME}" /FO LIST /V',
            f'schtasks /Run /TN "{WINDOWS_TASK_NAME}"',
            f'schtasks /End /TN "{WINDOWS_TASK_NAME}"',
        ]

    def _user_id(self) -> str:
        domain = os.environ.get("USERDOMAIN", "")
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "hebb"
        return f"{domain}\\{user}" if domain else user

    def _wrapper_script(self) -> Path:
        """A small ``.cmd`` wrapper that captures stdout/stderr to %TEMP%\\hebb.log."""
        appdata = os.environ.get("LOCALAPPDATA") or str(Path.home())
        wrapper = Path(appdata) / "HebbMind" / "hebb-serve.cmd"
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        cmd_argv = hebb_command() + ["_serve"]
        # Quote each arg for cmd.exe — paths may contain spaces.
        quoted = " ".join(f'"{a}"' if " " in a else a for a in cmd_argv)
        wrapper.write_text(
            f'@echo off\r\ncd /d "{workspace_dir()}"\r\n{quoted} 1>"%TEMP%\\hebb.log" 2>"%TEMP%\\hebb.err"\r\n'
        )
        return wrapper

    def _task_xml(self) -> str:
        wrapper = self._wrapper_script()
        user_id = self._user_id()
        if self.scope == "system":
            principal = (
                '<Principal id="Author">\n'
                "      <UserId>S-1-5-18</UserId>\n"  # SYSTEM
                "      <RunLevel>HighestAvailable</RunLevel>\n"
                "    </Principal>"
            )
        else:
            principal = (
                '<Principal id="Author">\n'
                f"      <UserId>{user_id}</UserId>\n"
                "      <LogonType>InteractiveToken</LogonType>\n"
                "      <RunLevel>LeastPrivilege</RunLevel>\n"
                "    </Principal>"
            )
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Hebb Mind background memory server</Description>
    <URI>\\{WINDOWS_TASK_NAME}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      {f"<UserId>{user_id}</UserId>" if self.scope == "user" else ""}
    </LogonTrigger>
    <BootTrigger>
      <Enabled>{"true" if self.scope == "system" else "false"}</Enabled>
    </BootTrigger>
  </Triggers>
  <Principals>
    {principal}
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>5</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{wrapper}</Command>
      <WorkingDirectory>{workspace_dir()}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""

    # Lifecycle ------------------------------------------------------------
    def install(self) -> None:
        if not shutil.which("schtasks"):
            raise ServiceError("schtasks.exe not found — is this really Windows?")
        # Task Scheduler reads UTF-16 XML; write with BOM.
        appdata = os.environ.get("LOCALAPPDATA") or str(Path.home())
        xml_path = Path(appdata) / "HebbMind" / f"{WINDOWS_TASK_NAME}.xml"
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        xml_path.write_text(self._task_xml(), encoding="utf-16")
        args = ["/Create", "/TN", WINDOWS_TASK_NAME, "/XML", str(xml_path), "/F"]
        if self.scope == "system":
            args.extend(["/RU", "SYSTEM"])
        result = _schtasks(args)
        if result.returncode != 0:
            raise ServiceError(
                f"schtasks /Create failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
            )
        # Run it now so the user does not have to logoff / reboot.
        self.start()

    def uninstall(self) -> None:
        if not self._exists():
            return
        self.stop()
        _schtasks(["/Delete", "/TN", WINDOWS_TASK_NAME, "/F"])

    def start(self) -> None:
        if not self._exists():
            raise ServiceNotInstalledError()
        result = _schtasks(["/Run", "/TN", WINDOWS_TASK_NAME])
        if result.returncode != 0:
            raise ServiceError(f"schtasks /Run failed: {result.stderr.strip()}")

    def stop(self) -> None:
        if not self._exists():
            return
        _schtasks(["/End", "/TN", WINDOWS_TASK_NAME])

    def status(self) -> ServiceStatus:
        if not self._exists():
            return ServiceStatus(installed=False, running=False, detail="not installed")
        result = _schtasks(["/Query", "/TN", WINDOWS_TASK_NAME, "/FO", "LIST", "/V"])
        running = "Running" in result.stdout
        # Pull the "Status:" line if present.
        detail = next(
            (line.strip() for line in result.stdout.splitlines() if line.strip().startswith("Status:")),
            "installed",
        )
        return ServiceStatus(installed=True, running=running, detail=detail)

    def _exists(self) -> bool:
        return _schtasks(["/Query", "/TN", WINDOWS_TASK_NAME]).returncode == 0


# ---------------------------------------------------------------------------
# Errors + factory
# ---------------------------------------------------------------------------


class ServiceError(RuntimeError):
    """Raised when a service operation fails."""


class ServiceNotInstalledError(ServiceError):
    """Raised when start/stop is called before install."""

    def __init__(self) -> None:
        super().__init__("Hebb Mind service is not installed. Run: hebb service install")


class UnsupportedPlatformError(ServiceError):
    """Raised when the current OS has no supported service backend."""


def get_manager(scope: Scope = "user") -> ServiceManager:
    """Return the right :class:`ServiceManager` for the current OS."""
    system = platform.system()
    if system == "Darwin":
        return LaunchdManager(scope)
    if system == "Linux":
        return SystemdManager(scope)
    if system == "Windows":
        return WindowsTaskManager(scope)
    raise UnsupportedPlatformError(f"Unsupported OS: {system}")
