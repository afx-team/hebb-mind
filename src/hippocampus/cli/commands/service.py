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
    """Return the working directory (where hippocampus.json lives)."""
    from hippocampus.config.loader import find_config_file

    config = find_config_file()
    return str(config.parent) if config else os.getcwd()


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
LAUNCHD_PATH = Path.home() / "Library" / "LaunchAgents" / "com.hippocampus.server.plist"


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
    console.print(f"[bold]Installing systemd service...[/]")
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
    console.print(f"[bold]Installing launchd service...[/]")
    console.print(f"  Plist: {LAUNCHD_PATH}")
    console.print(f"  Working dir: {_working_dir()}")
    console.print(f"  Command: {_hippocampus_bin()} start")
    console.print()

    LAUNCHD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHD_PATH.write_text(plist)

    subprocess.run(["launchctl", "load", str(LAUNCHD_PATH)], check=True)
    console.print("[green]Service installed and started.[/]")
    console.print("  Logs:    [cmd]tail -f /tmp/hippocampus.log[/]")
    console.print("  Stop:    [cmd]launchctl unload {}[/]".format(LAUNCHD_PATH))
    console.print("  Restart: [cmd]launchctl unload {} && launchctl load {}[/]".format(LAUNCHD_PATH, LAUNCHD_PATH))


def _uninstall_launchd() -> None:
    if not LAUNCHD_PATH.exists():
        console.print("[yellow]Service not installed.[/]")
        return

    console.print("[bold]Uninstalling launchd service...[/]")
    subprocess.run(["launchctl", "unload", str(LAUNCHD_PATH)], check=False)
    LAUNCHD_PATH.unlink()
    console.print("[green]Service uninstalled.[/]")