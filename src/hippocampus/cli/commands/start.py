"""hippocampus start — launch the API server."""

from __future__ import annotations

import click
from rich.console import Console

from hippocampus import __version__
from hippocampus.config.loader import load_settings

console = Console()


@click.command("start")
@click.option("--host", default=None, help="Override host")
@click.option("--port", default=None, type=int, help="Override port")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev mode)")
def start_cmd(host: str | None, port: int | None, reload: bool) -> None:
    """Start the hippocampus API server."""
    import uvicorn

    settings = load_settings()
    final_host = host or settings.host
    final_port = port or settings.port

    console.print(f"[bold green]Hippocampus v{__version__}[/]")
    console.print(f"  Server:  http://{final_host}:{final_port}")
    console.print(f"  Docs:    http://{final_host}:{final_port}/docs")
    console.print(f"  Model:   {settings.llm_model}")
    console.print(f"  DB:      {settings.db_path}")
    console.print()

    uvicorn.run(
        "hippocampus.server.app:app",
        host=final_host,
        port=final_port,
        reload=reload,
        log_level="info",
    )
