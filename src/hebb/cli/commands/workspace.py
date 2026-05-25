"""hebb workspace — show the resolved workspace directory."""

from __future__ import annotations

import click
from rich.console import Console

from hebb.config.workspace import resolve_workspace

console = Console()


@click.command("workspace")
def workspace_cmd() -> None:
    """Show the resolved workspace directory.

    The workspace is resolved with the following priority:
      1. HEBB_HOME environment variable
      2. Parent directory of hebb.json (walked up from CWD)
      3. ~/.hebb/ (global default)
    """
    workspace = resolve_workspace()
    console.print(str(workspace))
