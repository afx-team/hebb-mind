"""hebb start — launch the API server."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

from hebb import __version__
from hebb.config.loader import load_settings
from hebb.config.workspace import resolve_workspace

console = Console()


def _pid_file() -> Path:
    """Return the PID file path (in the workspace root)."""
    workspace = resolve_workspace()
    return workspace / "hebb.pid"


def _write_pid(pid: int) -> None:
    _pid_file().write_text(str(pid))


def _read_pid() -> int | None:
    f = _pid_file()
    if f.exists():
        try:
            return int(f.read_text().strip())
        except (ValueError, OSError):
            return None
    return None


def _remove_pid() -> None:
    f = _pid_file()
    if f.exists():
        f.unlink()


def _is_server_running(url: str) -> bool:
    """Check if the server is reachable."""
    import httpx

    try:
        httpx.get(f"{url}/health", timeout=3)
        return True
    except (httpx.ConnectError, httpx.RemoteProtocolError):
        return False


@click.command("start")
@click.option("--host", default=None, help="Override host")
@click.option("--port", default=None, type=int, help="Override port")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev mode)")
@click.option("-d", "--daemon", is_flag=True, help="Run as background daemon")
def start_cmd(host: str | None, port: int | None, reload: bool, daemon: bool) -> None:
    """Start the hebb API server."""
    settings = load_settings()
    final_host = host or settings.host
    final_port = port or settings.port
    url = f"http://{'127.0.0.1' if final_host in ('0.0.0.0', '') else final_host}:{final_port}"

    # Already running?
    if _is_server_running(url):
        console.print(f"[yellow]Server already running at {url}[/]")
        return

    if daemon:
        _start_daemon(final_host, final_port, reload)
        return

    _run_foreground(final_host, final_port, reload, settings)


def _start_daemon(host: str, port: int, reload: bool) -> None:
    """Spawn the server as a background process."""
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}"

    # Build command: hebb start (without --daemon)
    cmd = [sys.executable, "-m", "hebb.cli.main", "start", "--host", host, "--port", str(port)]
    if reload:
        cmd.append("--reload")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    _write_pid(process.pid)
    console.print(f"[bold green]Hebb Mind started in daemon mode[/] (PID {process.pid})")

    # Wait briefly to confirm startup
    import time

    for _ in range(20):
        time.sleep(0.5)
        if _is_server_running(url):
            console.print(f"  Server:     {url}")
            console.print(f"  Docs:       {url}/docs")
            return

    # Check if process is still alive
    if process.poll() is not None:
        _remove_pid()
        console.print("[red]Server failed to start. Run without --daemon to see errors.[/]")
        raise SystemExit(1)

    console.print("[yellow]Server is starting... Check status: hebb status[/]")


def _run_foreground(host: str, port: int, reload: bool, settings: object) -> None:
    """Run the server in the foreground."""
    import uvicorn

    workspace = settings.home_dir or resolve_workspace()

    console.print(f"[bold green]Hebb Mind v{__version__}[/]")
    console.print(f"  Workspace:  {workspace}")
    console.print(f"  Server:     http://{host}:{port}")
    console.print(f"  Docs:       http://{host}:{port}/docs")
    console.print(f"  LLM:        {settings.llm_model or '[dim]not configured[/]'}")
    console.print(f"  DB:         {settings.db_path}")

    # Embedding status
    if not settings.embedding_enabled:
        console.print("  Embedding:  [yellow]disabled[/]")
    elif settings.embedding_provider == "api":
        console.print(f"  Embedding:  [cyan]{settings.embedding_model}[/] (API)")
    else:
        from hebb.embedding.local import is_model_cached

        cached = is_model_cached(settings.embedding_model)
        status = "[green]cached[/]" if cached else "[yellow]will download on startup[/]"
        console.print(f"  Embedding:  [cyan]{settings.embedding_model}[/] ({status})")

    console.print()

    uvicorn.run(
        "hebb.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
