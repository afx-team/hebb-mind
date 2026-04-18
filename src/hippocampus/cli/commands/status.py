"""hippocampus status — check running server status."""

from __future__ import annotations

import click
import httpx
from rich.console import Console
from rich.table import Table

from hippocampus.config.loader import load_settings

console = Console()


@click.command("status")
@click.option("--url", default=None, help="Server URL (default: from config)")
def status_cmd(url: str | None) -> None:
    """Check the status of a running hippocampus server."""
    if not url:
        settings = load_settings()
        host = settings.host if settings.host != "0.0.0.0" else "127.0.0.1"
        url = f"http://{host}:{settings.port}"

    try:
        health = httpx.get(f"{url}/health", timeout=5).json()
        status_data = httpx.get(f"{url}/status", timeout=5).json()
    except (httpx.ConnectError, httpx.RemoteProtocolError):
        console.print(f"[red]Cannot connect to {url}[/]")
        raise SystemExit(1)

    console.print(f"[green]Server is running[/] (v{health.get('version', '?')})")

    # Scheduler info
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
