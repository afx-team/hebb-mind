"""hebb stop / restart — manage server lifecycle."""

from __future__ import annotations

import signal

import click
import httpx
from rich.console import Console

from hebb.config.loader import load_settings

console = Console()


def _resolve_url(url: str | None) -> str:
    if url:
        return url
    settings = load_settings()
    host = settings.host if settings.host != "0.0.0.0" else "127.0.0.1"
    return f"http://{host}:{settings.port}"


def _stop_server(url: str) -> bool:
    """Stop the running server. Returns True if stopped."""
    settings = load_settings()
    port = settings.port

    # Check if server is running
    try:
        httpx.get(f"{url}/health", timeout=3)
    except (httpx.ConnectError, httpx.RemoteProtocolError):
        console.print(f"[yellow]No server running at {url}[/]")
        # Clean stale PID file
        from hebb.cli.commands.start import _remove_pid

        _remove_pid()
        return False

    # Try PID file first (daemon mode)
    from hebb.cli.commands.start import _read_pid, _remove_pid

    pid = _read_pid()
    pids = []
    if pid:
        import os

        try:
            os.kill(pid, signal.SIGTERM)
            pids.append(pid)
        except (ProcessLookupError, PermissionError):
            pass
        _remove_pid()

    # Fallback: find by port
    if not pids:
        pids = _find_server_pids(port)

    if not pids:
        console.print(f"[red]Server is running but cannot find PID on port {port}[/]")
        return False

    # Kill any remaining PIDs
    import os

    for p in pids:
        try:
            os.kill(p, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

    console.print(f"[green]Server stopped[/] (PID {', '.join(str(p) for p in pids)})")
    return True


def _find_server_pids(port: int) -> list[int]:
    """Find all PIDs listening on the given port."""
    import subprocess

    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return []


@click.command("stop")
@click.option("--url", default=None, help="Server URL (default: from config)")
def stop_cmd(url: str | None) -> None:
    """Stop the running hebb server."""
    _stop_server(_resolve_url(url))


@click.command("restart")
@click.option("--host", default=None, help="Override host")
@click.option("--port", default=None, type=int, help="Override port")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev mode)")
@click.option("-d", "--daemon", is_flag=True, help="Run as background daemon")
def restart_cmd(host: str | None, port: int | None, reload: bool, daemon: bool) -> None:
    """Restart the hebb server (stop + start)."""
    import time

    url = _resolve_url(None)
    stopped = _stop_server(url)
    if stopped:
        time.sleep(1)

    # Import and call start directly
    from hebb.cli.commands.start import start_cmd

    ctx = click.Context(start_cmd)
    ctx.invoke(start_cmd, host=host, port=port, reload=reload, daemon=daemon)
