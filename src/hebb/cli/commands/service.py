"""hebb service — install and control the Hebb Mind background service.

The OS service manager (launchd / systemd / Task Scheduler) is the only
supported way to run Hebb Mind. This command group manages that service.

Defaults are no-admin (``--scope user``):
  * macOS:   LaunchAgent in ``~/Library/LaunchAgents``
  * Linux:   systemd ``--user`` unit in ``~/.config/systemd/user``
  * Windows: per-user Scheduled Task (interactive logon, LeastPrivilege)

Use ``--scope system`` for system-wide auto-start; that path requires
admin/sudo elevation and Hebb Mind will prompt for it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click
import httpx
from rich.console import Console

from hebb.cli._url import resolve_server_url
from hebb.utils.service_manager import (
    HomeConflictError,
    ServiceError,
    ServiceManager,
    ServiceNotInstalledError,
    UnsupportedPlatformError,
    get_manager,
    resolve_service_home,
)

console = Console()


def _wait_until_healthy(url: str, attempts: int = 30, interval: float = 0.5) -> bool:
    """Poll ``/health`` until the server responds or attempts run out."""
    import time

    for _ in range(attempts):
        try:
            httpx.get(f"{url}/health", timeout=2)
            return True
        except (
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            httpx.ReadError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        ):
            time.sleep(interval)
    return False


def _scope_option(default: str = "user") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    return click.option(
        "--scope",
        type=click.Choice(["user", "system"]),
        default=default,
        show_default=True,
        help="Install as a per-user service (no admin) or system-wide (requires admin/sudo).",
    )


def _print_post_install(manager: ServiceManager, url: str) -> None:
    console.print(f"  Web Console:  [cyan]{url}/[/]")
    console.print("  →             [cmd]hebb console[/] (open in browser)")
    if manager.logs_hint:
        console.print(f"  Logs:         [cmd]{manager.logs_hint}[/]")
    for hint in manager.manage_hints:
        console.print(f"  →             [cmd]{hint}[/]")


def _print_service_error(err: ServiceError) -> None:
    console.print(f"[red]{err}[/]")
    raise SystemExit(1)


@click.group("service")
def service_cmd() -> None:
    """Install and control the Hebb Mind background service."""


@service_cmd.command("install")
@_scope_option()
@click.option(
    "--home",
    type=click.Path(file_okay=False, dir_okay=True, path_type=str),
    default=None,
    help="Absolute workspace/home the service binds to. Defaults to $HEBB_HOME or ~/.hebb. "
    "Pinned into the unit so the daemon's DB is independent of the install directory.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-point the service even if it is already installed against a different home.",
)
def service_install(scope: str, home: str | None, force: bool) -> None:
    """Install Hebb Mind as a background service and start it."""
    resolved_home = resolve_service_home(home)
    try:
        manager = get_manager(scope=scope, home=resolved_home)  # type: ignore[arg-type]
    except UnsupportedPlatformError as exc:
        console.print(f"[red]{exc}[/]")
        raise SystemExit(1)

    console.print(f"[bold]Installing {manager.display_name} service...[/]")
    console.print(f"  Workspace: [cyan]{resolved_home}[/]")
    if manager.install_path:
        console.print(f"  Artifact: [dim]{manager.install_path}[/]")
    if scope == "system":
        console.print("  [yellow]System scope requires admin/sudo — you may be prompted.[/]")

    try:
        manager.install(force=force)
    except HomeConflictError as exc:
        console.print(f"[red]{exc}[/]")
        raise SystemExit(1)
    except ServiceError as exc:
        _print_service_error(exc)

    url = resolve_server_url()
    if _wait_until_healthy(url):
        console.print(f"[green]Hebb Mind is running[/] at {url}")
    else:
        console.print(f"[yellow]Service installed but {url}/health did not respond yet.[/]")
        console.print("  Check logs (above) or run: [cmd]hebb status[/]")
    _print_post_install(manager, url)


@service_cmd.command("uninstall")
@_scope_option()
def service_uninstall(scope: str) -> None:
    """Stop the service and remove its OS registration."""
    try:
        manager = get_manager(scope=scope)  # type: ignore[arg-type]
    except UnsupportedPlatformError as exc:
        console.print(f"[red]{exc}[/]")
        raise SystemExit(1)

    status = manager.status()
    if not status.installed:
        console.print("[yellow]Service is not installed.[/]")
        return

    try:
        manager.uninstall()
    except ServiceError as exc:
        _print_service_error(exc)
    console.print(f"[green]{manager.display_name} service uninstalled.[/]")


@service_cmd.command("start")
@_scope_option()
def service_start(scope: str) -> None:
    """Start the installed service."""
    manager = _resolve_manager(scope)
    try:
        manager.start()
    except ServiceNotInstalledError as exc:
        console.print(f"[yellow]{exc}[/]")
        raise SystemExit(1)
    except ServiceError as exc:
        _print_service_error(exc)

    url = resolve_server_url()
    if _wait_until_healthy(url):
        console.print(f"[green]Hebb Mind is running[/] at {url}")
    else:
        console.print("[yellow]Service started but health check did not respond yet.[/]")


@service_cmd.command("stop")
@_scope_option()
def service_stop(scope: str) -> None:
    """Stop the running service (leaves it installed)."""
    manager = _resolve_manager(scope)
    try:
        manager.stop()
    except ServiceError as exc:
        _print_service_error(exc)
    console.print(f"[green]{manager.display_name} service stopped.[/]")


@service_cmd.command("restart")
@_scope_option()
def service_restart(scope: str) -> None:
    """Restart the service."""
    manager = _resolve_manager(scope)
    try:
        manager.restart()
    except ServiceNotInstalledError as exc:
        console.print(f"[yellow]{exc}[/]")
        raise SystemExit(1)
    except ServiceError as exc:
        _print_service_error(exc)
    url = resolve_server_url()
    if _wait_until_healthy(url):
        console.print(f"[green]Hebb Mind restarted[/] at {url}")
    else:
        console.print("[yellow]Restart issued but health check did not respond.[/]")


def _resolve_manager(scope: str) -> ServiceManager:
    try:
        return get_manager(scope=scope)  # type: ignore[arg-type]
    except UnsupportedPlatformError as exc:
        console.print(f"[red]{exc}[/]")
        raise SystemExit(1)
