"""hebb _serve — internal foreground server entrypoint.

This command is **not** part of the public CLI. It exists only as the
process the OS service manager (launchd / systemd / Task Scheduler)
invokes — that is the single supported way to start the server. End
users should use ``hebb service install`` / ``hebb service start``.
"""

from __future__ import annotations

import click


@click.command("_serve", hidden=True)
@click.option("--host", default=None, help="Override host from config")
@click.option("--port", default=None, type=int, help="Override port from config")
def serve_cmd(host: str | None, port: int | None) -> None:
    """Run the Hebb Mind API server in the foreground (used by the OS service manager)."""
    import uvicorn

    from hebb.config.loader import load_settings

    settings = load_settings()
    final_host = host or settings.host
    final_port = port or settings.port

    uvicorn.run(
        "hebb.server.app:app",
        host=final_host,
        port=final_port,
        log_level="info",
    )
