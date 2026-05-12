"""hippocampus init — initialize a project directory."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console

from hippocampus.config.loader import create_default_config, load_settings
from hippocampus.config.settings import Settings
from hippocampus.config.workspace import get_default_home
from hippocampus.storage.factory import create_stores

console = Console()


@dataclass(frozen=True)
class InitResult:
    """Result of workspace initialization."""

    settings_path: Path
    settings: Settings


def default_init_target() -> Path:
    """Return the default initialization target directory.

    Args:
        None.

    Returns:
        HIPPOCAMPUS_HOME when set, otherwise ~/.hippocampus.
    """
    env_home = os.environ.get("HIPPOCAMPUS_HOME")
    if env_home:
        return Path(env_home).resolve()
    return get_default_home()


def initialize_workspace(target_dir: str | Path | None = None, force: bool = False) -> InitResult:
    """Initialize a Hippocampus workspace.

    Args:
        target_dir: Directory to initialize. Defaults to HIPPOCAMPUS_HOME or ~/.hippocampus.
        force: Whether to overwrite config and reset SQLite storage.

    Returns:
        Initialized settings path and loaded settings.
    """
    target = Path(target_dir).resolve() if target_dir else default_init_target()
    target.mkdir(parents=True, exist_ok=True)

    config_path = target / "hippocampus.json"

    if not config_path.exists() or force:
        create_default_config(config_path)

    settings = load_settings(config_path)

    if force and settings.storage_type == "sqlite":
        db_path = Path(settings.db_path)
        for suffix in ("", "-wal", "-shm"):
            p = db_path.parent / (db_path.name + suffix)
            if p.exists():
                p.unlink()

    async def _init_storage():
        ctx = await create_stores(settings)
        await ctx.partition_store.ensure_defaults()
        await ctx.close()

    asyncio.run(_init_storage())

    kg_path = Path(settings.kg_path)
    if force or not kg_path.exists():
        kg_path.parent.mkdir(parents=True, exist_ok=True)
        kg_path.write_text(json.dumps({"nodes": [], "edges": [], "version": 1}, indent=2))

    return InitResult(settings_path=config_path, settings=settings)


@click.command("init")
@click.option(
    "--dir",
    "target_dir",
    default=None,
    help="Directory to initialize (default: HIPPOCAMPUS_HOME or ~/.hippocampus/)",
)
@click.option("--force", is_flag=True, help="Overwrite existing config")
def init_cmd(target_dir: str | None, force: bool) -> None:
    """Initialize a hippocampus project directory.

    If --dir is not specified, defaults to ~/.hippocampus/ (global workspace).
    """
    target = Path(target_dir).resolve() if target_dir else default_init_target()
    config_path = target / "hippocampus.json"
    existed = config_path.exists()
    kg_path = target / "knowledge_graph.json"
    kg_existed = kg_path.exists()

    result = initialize_workspace(target, force=force)
    settings = result.settings

    if existed and not force:
        console.print(f"[yellow]Config already exists:[/] {result.settings_path}")
    else:
        console.print(f"[green]Created config:[/] {result.settings_path}")

    if force and settings.storage_type == "sqlite":
        console.print(f"[yellow]Reset SQLite database:[/] {settings.db_path}")

    console.print(f"[green]Initialized storage:[/] {settings.storage_type}")

    if force or not kg_existed:
        console.print(f"[green]Created knowledge graph:[/] {settings.kg_path}")

    console.print()
    console.print("[bold]Hippocampus initialized![/]")
    console.print(f"  Workspace: [cyan]{settings.home_dir}[/]")
    console.print(f"  Database:  [dim]{settings.db_path}[/]")
    console.print(f"  Graph:     [dim]{settings.kg_path}[/]")
    console.print()
    console.print("Next steps:")
    console.print("  1. For the default out-of-box setup:")
    console.print("     [cyan]hippocampus setup[/]")
    console.print()
    console.print("  2. Or start directly with the current config:")
    console.print("     [cyan]hippocampus start[/]")
    console.print()
    console.print(f"  Web Console: [cyan]http://localhost:{settings.port}/[/]")
