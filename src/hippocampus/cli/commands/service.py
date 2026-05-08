"""hippocampus service — install/uninstall system service for auto-start."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


def _hippocampus_bin() -> str:
    """Return the absolute path to the hippocampus CLI binary."""
    # Prefer the executable that's currently running
    cli_path = shutil.which("hippocampus")
    if cli_path:
        return cli_path
    # Fallback: python -m invocation
    return f"{sys.executable} -m hippocampus.cli.main"


def _working_dir() -> str:
    """Return the working directory (workspace root)."""
    from hippocampus.config.workspace import resolve_workspace

    return str(resolve_workspace())


def _systemd_unit() -> str:
    """Generate a systemd unit file."""
    bin_path = _hippocampus_bin()
    work_dir = _working_dir()
    user = os.environ.get("USER", "hippocampus")

    return f"""[Unit]
Description=Hippocampus Memory Server
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={work_dir}
ExecStart={bin_path} start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def _launchd_plist() -> str:
    """Generate a launchd plist file."""
    bin_path = _hippocampus_bin()
    work_dir = _working_dir()

    # launchd doesn't support shell-style "python -m", split if needed
    if " " in bin_path:
        program_args = bin_path.split() + ["start"]
    else:
        program_args = [bin_path, "start"]

    args_xml = "\n".join(f"    <string>{a}</string>" for a in program_args)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hippocampus.server</string>
  <key>ProgramArguments</key>
  <array>
{args_xml}
  </array>
  <key>WorkingDirectory</key>
  <string>{work_dir}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/hippocampus.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/hippocampus.err</string>
</dict>
</plist>
"""


SYSTEMD_PATH = Path("/etc/systemd/system/hippocampus.service")
LAUNCHD_LABEL = "com.hippocampus.server"
LAUNCHD_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


@click.group("service")
def service_cmd() -> None:
    """Manage system service (auto-start on boot)."""
    pass


@service_cmd.command("install")
def service_install() -> None:
    """Install Hippocampus as a system service (auto-start on boot)."""
    system = platform.system()

    if system == "Linux":
        _install_systemd()
    elif system == "Darwin":
        _install_launchd()
    else:
        console.print(f"[red]Unsupported OS: {system}[/]")
        raise SystemExit(1)


@service_cmd.command("uninstall")
def service_uninstall() -> None:
    """Uninstall the system service."""
    system = platform.system()

    if system == "Linux":
        _uninstall_systemd()
    elif system == "Darwin":
        _uninstall_launchd()
    else:
        console.print(f"[red]Unsupported OS: {system}[/]")
        raise SystemExit(1)


def _install_systemd() -> None:
    unit = _systemd_unit()
    console.print("[bold]Installing systemd service...[/]")
    console.print(f"  Unit file: {SYSTEMD_PATH}")
    console.print(f"  Working dir: {_working_dir()}")
    console.print(f"  Command: {_hippocampus_bin()} start")
    console.print()

    # Write unit file
    try:
        SYSTEMD_PATH.write_text(unit)
    except PermissionError:
        console.print(f"[yellow]Need sudo to write {SYSTEMD_PATH}[/]")
        subprocess.run(["sudo", "tee", str(SYSTEMD_PATH)], input=unit, text=True, check=True)

    # Reload and enable
    cmds = [
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "hippocampus"],
        ["systemctl", "start", "hippocampus"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            console.print(f"[yellow]Need sudo for: {' '.join(cmd)}[/]")
            subprocess.run(["sudo", *cmd], check=True)
        except FileNotFoundError:
            console.print(f"[red]Command not found: {cmd[0]}. Is systemd installed?[/]")
            raise SystemExit(1)

    console.print("[green]Service installed and started.[/]")
    console.print("  Status:  [cmd]systemctl status hippocampus[/]")
    console.print("  Logs:    [cmd]journalctl -u hippocampus -f[/]")
    console.print("  Stop:    [cmd]systemctl stop hippocampus[/]")


def _uninstall_systemd() -> None:
    if not SYSTEMD_PATH.exists():
        console.print("[yellow]Service not installed.[/]")
        return

    console.print("[bold]Uninstalling systemd service...[/]")
    cmds = [
        ["systemctl", "stop", "hippocampus"],
        ["systemctl", "disable", "hippocampus"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            subprocess.run(["sudo", *cmd], check=True)

    try:
        SYSTEMD_PATH.unlink()
    except PermissionError:
        subprocess.run(["sudo", "rm", str(SYSTEMD_PATH)], check=True)

    subprocess.run(["systemctl", "daemon-reload"], check=False)
    console.print("[green]Service uninstalled.[/]")


def _install_launchd() -> None:
    plist = _launchd_plist()
    console.print("[bold]Installing launchd service...[/]")
    console.print(f"  Plist: {LAUNCHD_PATH}")
    console.print(f"  Working dir: {_working_dir()}")
    console.print(f"  Command: {_hippocampus_bin()} start")
    console.print()

    LAUNCHD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHD_PATH.write_text(plist)

    _load_launchd_service()
    console.print("[green]Service installed and loaded.[/]")
    console.print("  Logs:    [cmd]tail -f /tmp/hippocampus.log[/]")
    console.print(f"  Status:  [cmd]launchctl print {_launchd_target()}[/]")
    console.print(f"  Stop:    [cmd]launchctl bootout {_launchd_domain()} {LAUNCHD_PATH}[/]")
    console.print(
        f"  Restart: [cmd]launchctl bootout {_launchd_domain()} {LAUNCHD_PATH} "
        f"&& launchctl bootstrap {_launchd_domain()} {LAUNCHD_PATH}[/]"
    )


def _uninstall_launchd() -> None:
    if not LAUNCHD_PATH.exists():
        console.print("[yellow]Service not installed.[/]")
        return

    console.print("[bold]Uninstalling launchd service...[/]")
    _unload_launchd_service()
    LAUNCHD_PATH.unlink()
    console.print("[green]Service uninstalled.[/]")


def _launchd_domain() -> str:
    """Return the launchd user GUI domain for LaunchAgents."""
    return f"gui/{os.getuid()}"


def _launchd_target() -> str:
    """Return the fully qualified launchd service target."""
    return f"{_launchd_domain()}/{LAUNCHD_LABEL}"


def _run_launchctl(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run launchctl and capture output for reliable error reporting."""
    return subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _launchd_is_loaded() -> bool:
    """Return whether launchd knows about the Hippocampus service."""
    result = _run_launchctl(["print", _launchd_target()])
    return result.returncode == 0


def _print_launchctl_failure(action: str, result: subprocess.CompletedProcess[str]) -> None:
    """Print launchctl output before failing."""
    console.print(f"[red]launchctl {action} failed[/] (exit {result.returncode})")
    if result.stderr.strip():
        console.print(result.stderr.strip())
    if result.stdout.strip():
        console.print(result.stdout.strip())


def _load_launchd_service() -> None:
    """Load the launchd service and verify it was registered."""
    # Replace any stale registration so repeated installs pick up plist changes.
    _unload_launchd_service()

    result = _run_launchctl(["bootstrap", _launchd_domain(), str(LAUNCHD_PATH)])
    if result.returncode != 0:
        legacy = _run_launchctl(["load", str(LAUNCHD_PATH)])
        if legacy.returncode != 0 and not _launchd_is_loaded():
            _print_launchctl_failure("bootstrap", result)
            _print_launchctl_failure("load", legacy)
            raise SystemExit(1)

    kickstart = _run_launchctl(["kickstart", "-k", _launchd_target()])
    if kickstart.returncode != 0 and not _launchd_is_loaded():
        _print_launchctl_failure("kickstart", kickstart)
        raise SystemExit(1)

    if not _launchd_is_loaded():
        console.print("[red]launchd did not register the Hippocampus service.[/]")
        raise SystemExit(1)


def _unload_launchd_service() -> None:
    """Unload the launchd service if it is currently registered."""
    result = _run_launchctl(["bootout", _launchd_domain(), str(LAUNCHD_PATH)])
    if result.returncode == 0 or not _launchd_is_loaded():
        return

    _run_launchctl(["unload", str(LAUNCHD_PATH)])
