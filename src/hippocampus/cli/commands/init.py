"""hippocampus init — initialize a project directory."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console

from hippocampus.config.loader import create_default_config, load_settings
from hippocampus.config.workspace import get_default_home
from hippocampus.storage.factory import create_stores

console = Console()


@click.command("init")
@click.option("--dir", "target_dir", default=None, help="Directory to initialize (default: ~/.hippocampus/)")
@click.option("--force", is_flag=True, help="Overwrite existing config")
def init_cmd(target_dir: str | None, force: bool) -> None:
    """Initialize a hippocampus project directory.

    If --dir is not specified, defaults to ~/.hippocampus/ (global workspace).
    """
    target = Path(target_dir).resolve() if target_dir else get_default_home()
    target.mkdir(parents=True, exist_ok=True)

    config_path = target / "hippocampus.json"

    # Step 1: Create config
    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists:[/] {config_path}")
    else:
        create_default_config(config_path)
        console.print(f"[green]Created config:[/] {config_path}")

    # Step 2: Initialize storage and default partitions
    settings = load_settings(config_path)

    # --force: delete existing database to start fresh
    if force and settings.storage_type == "sqlite":
        db_path = Path(settings.db_path)
        for suffix in ("", "-wal", "-shm"):
            p = db_path.parent / (db_path.name + suffix)
            if p.exists():
                p.unlink()
        console.print(f"[yellow]Removed existing database:[/] {db_path}")

    async def _init_storage():
        ctx = await create_stores(settings)
        await ctx.partition_store.ensure_defaults()
        await ctx.close()

    asyncio.run(_init_storage())
    console.print(f"[green]Initialized storage:[/] {settings.storage_type}")

    # Step 3: Create empty knowledge graph (--force: always overwrite)
    kg_path = Path(settings.kg_path)
    if force or not kg_path.exists():
        kg_path.parent.mkdir(parents=True, exist_ok=True)
        kg_path.write_text(json.dumps({"nodes": [], "edges": [], "version": 1}, indent=2))
        console.print(f"[green]Created knowledge graph:[/] {kg_path}")

    # Step 4: Print next steps
    console.print()
    console.print("[bold]Hippocampus initialized![/]")
    console.print(f"  Workspace: [cyan]{settings.home_dir}[/]")
    console.print(f"  Database:  [dim]{settings.db_path}[/]")
    console.print(f"  Graph:     [dim]{settings.kg_path}[/]")
    console.print()
    console.print("Next steps:")
    console.print("  1. Configure your LLM:")
    console.print("     [cyan]hippocampus config set llm_api_key sk-your-key[/]")
    console.print("     [cyan]hippocampus config set llm_model openai/gpt-4o-mini[/]")
    console.print()
    console.print("  2. Start the server:")
    console.print("     [cyan]hippocampus start[/]")
    console.print()
    console.print(f"  3. Open Web Console: [cyan]http://localhost:{settings.port}/[/]")
