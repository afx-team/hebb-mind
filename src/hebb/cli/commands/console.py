"""hebb console — open the Web Console in a browser."""

from __future__ import annotations

import click
import httpx
from rich.console import Console

from hebb.cli._url import resolve_server_url

console = Console()


@click.command("console")
@click.option("--print", "print_only", is_flag=True, help="Print the URL without opening a browser.")
def console_cmd(print_only: bool) -> None:
    """Open the Hebb Mind Web Console in your default browser."""
    url = resolve_server_url()

    try:
        httpx.get(f"{url}/health", timeout=2)
    except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout, httpx.ConnectTimeout):
        console.print(f"[red]Cannot reach {url}[/]")
        console.print("  Install/start the background service: [cyan]hebb service install[/]")
        raise SystemExit(1)

    if print_only:
        console.print(url)
        return

    console.print(f"Opening [cyan]{url}/[/] ...")
    click.launch(f"{url}/")
