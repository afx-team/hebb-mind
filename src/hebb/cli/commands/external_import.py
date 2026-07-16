"""CLI command for importing external Markdown memory corpora."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from hebb import HebbMind, HebbMindError
from hebb.ingest.external import (
    SUPPORTED_EXTERNAL_SOURCES,
    ExternalImportError,
    import_external_corpus,
)

console = Console()


@click.command("import")
@click.argument("source", type=click.Choice(SUPPORTED_EXTERNAL_SOURCES, case_sensitive=False))
@click.argument(
    "path",
    type=click.Path(exists=True, readable=True, path_type=Path),
)
def import_cmd(source: str, path: Path) -> None:
    """Import SOURCE Markdown memories from PATH into Hebb Mind.

    SOURCE is one of ``openhands``, ``openclaw``, or ``hkuds``. PATH may
    point at the framework's workspace/repository root, its memory directory,
    or one Markdown file.

    Args:
        source: External framework identifier selected by Click.
        path: Existing corpus path selected by Click.

    Returns:
        None.

    Raises:
        click.ClickException: If discovery, parsing, embedding, or storage fails.
    """
    try:
        with HebbMind() as mind:
            summary = import_external_corpus(source, path, mind)
    except (ExternalImportError, HebbMindError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(
        f"[green]Import complete:[/] {summary.imported} imported, "
        f"{summary.skipped_existing} already present, {summary.discovered} discovered."
    )


__all__ = ["import_cmd"]
