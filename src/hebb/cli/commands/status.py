"""hebb status — show service registration, server health, and scheduler jobs."""

from __future__ import annotations

import platform

import click
import httpx
from rich.console import Console
from rich.table import Table

from hebb.cli._url import resolve_server_url
from hebb.utils.service_manager import (
    UnsupportedPlatformError,
    get_manager,
)

console = Console()


@click.command("status")
@click.option("--url", default=None, help="Server URL (default: from config)")
def status_cmd(url: str | None) -> None:
    """Show service registration, server health, and scheduler jobs."""
    _print_service_registration()

    if not url:
        url = resolve_server_url()

    try:
        health = httpx.get(f"{url}/health", timeout=5).json()
        status_data = httpx.get(f"{url}/status", timeout=5).json()
    except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout):
        console.print(f"[red]Cannot connect to {url}[/]")
        console.print("  Install/start the background service: [cyan]hebb service install[/]")
        raise SystemExit(1)

    console.print(f"[green]Server is running[/] at {url} (v{health.get('version', '?')})")

    scheduler = status_data.get("scheduler", {})
    if scheduler.get("running"):
        table = Table(title="Scheduler Jobs")
        table.add_column("Job")
        table.add_column("Next Run")
        for job_id, info in scheduler.get("jobs", {}).items():
            table.add_row(job_id, info.get("next_run_time", "N/A"))
        console.print(table)
    else:
        console.print("[yellow]Scheduler is not running[/]")


def _print_service_registration() -> None:
    """Print the OS service-manager registration status (one section)."""
    try:
        manager = get_manager()
    except UnsupportedPlatformError as exc:
        console.print(f"[yellow]Service manager: {exc}[/]")
        return

    state = manager.status()
    console.print(f"[bold]{manager.display_name}[/] (OS: {platform.system()})")
    console.print(f"  Installed: {'[green]yes[/]' if state.installed else '[yellow]no[/]'}")
    if state.installed:
        console.print(f"  Running:   {'[green]yes[/]' if state.running else '[yellow]no[/]'}")
        if state.detail:
            console.print(f"  Detail:    {state.detail}")
        if manager.install_path:
            console.print(f"  Artifact:  [dim]{manager.install_path}[/]")
        if manager.logs_hint:
            console.print(f"  Logs:      [cmd]{manager.logs_hint}[/]")
    else:
        console.print("  → Install with: [cmd]hebb service install[/]")
    console.print()
