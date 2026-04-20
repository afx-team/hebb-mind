"""hippocampus stop / restart — manage server lifecycle."""

from __future__ import annotations

import signal

import click
import httpx
from rich.console import Console

from hippocampus.config.loader import load_settings

console = Console()


def _resolve_url(url: str | None) -> str:
    if url:
        return url
    settings = load_settings()
    host = settings.host if settings.host != "0.0.0.0" else "127.0.0.1"
    return f"http://{host}:{settings.port}"


def _find_server_pids(port: int) -> list[int]:
    """Find all PIDs listening on the given port."""
    import subprocess

    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return []


def _stop_server(url: str) -> bool:
    """Stop the running server. Returns True if stopped."""
    settings = load_settings()
    port = settings.port

    # Check if server is running
    try:
        httpx.get(f"{url}/health", timeout=3)
    except (httpx.ConnectError, httpx.RemoteProtocolError):
        console.print(f"[yellow]No server running at {url}[/]")
        return False

    pids = _find_server_pids(port)
    if not pids:
        console.print(f"[red]Server is running but cannot find PID on port {port}[/]")
        return False

    import os
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

    console.print(f"[green]Server stopped[/] (PID {', '.join(str(p) for p in pids)})")
    return True


@click.command("stop")
@click.option("--url", default=None, help="Server URL (default: from config)")
def stop_cmd(url: str | None) -> None:
    """Stop the running hippocampus server."""
    _stop_server(_resolve_url(url))


@click.command("restart")
@click.option("--host", default=None, help="Override host")
@click.option("--port", default=None, type=int, help="Override port")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev mode)")
def restart_cmd(host: str | None, port: int | None, reload: bool) -> None:
    """Restart the hippocampus server (stop + start)."""
    import time

    url = _resolve_url(None)
    stopped = _stop_server(url)
    if stopped:
        time.sleep(1)

    # Import and call start directly
    from hippocampus.cli.commands.start import start_cmd
    ctx = click.Context(start_cmd)
    ctx.invoke(start_cmd, host=host, port=port, reload=reload)
