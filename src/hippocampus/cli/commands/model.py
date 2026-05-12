"""hippocampus model — inspect and prefetch embedding models."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from hippocampus.config.loader import find_config_file, load_settings, update_config_field
from hippocampus.embedding.catalog import (
    MODEL_DIMS,
    REGION_CHOICES,
    model_cache_dir,
    prefetch_model,
    resolve_region,
    workspace_model_available,
)
from hippocampus.embedding.local import is_model_cached

console = Console()


@click.group("model")
def model_cmd() -> None:
    """Manage embedding models."""


@model_cmd.command("status")
def model_status() -> None:
    """Show current embedding model status."""
    settings = load_settings()
    workspace = settings.home_dir
    if workspace is None:
        raise click.ClickException("Workspace could not be resolved")

    model_id = settings.embedding_model
    local_path = model_cache_dir(workspace, model_id)
    workspace_cached = workspace_model_available(workspace, model_id)
    cached = is_model_cached(model_id)
    source = settings.hf_endpoint or "HuggingFace official"

    table = Table(title="Embedding Model")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("enabled", str(settings.embedding_enabled))
    table.add_row("provider", settings.embedding_provider)
    table.add_row("model", model_id)
    table.add_row("dimension", str(settings.embedding_dim))
    table.add_row("known_dimension", str(MODEL_DIMS.get(model_id, "unknown")))
    table.add_row("language_strategy", _infer_language_strategy(model_id))
    table.add_row("download_source", source)
    table.add_row("workspace_path", str(local_path))
    table.add_row("workspace_cached", str(workspace_cached))
    table.add_row("available", str(cached))
    console.print(table)


@model_cmd.command("prefetch")
@click.option("--model", "model_id", default=None, help="Model ID to prefetch (default: current config)")
@click.option("--region", type=click.Choice(REGION_CHOICES), default="auto", show_default=True)
def model_prefetch(model_id: str | None, region: str) -> None:
    """Download an embedding model into the workspace."""
    config_path = find_config_file()
    if not config_path:
        raise click.ClickException("No hippocampus.json found. Run: hippocampus setup")

    settings = load_settings(config_path)
    workspace = settings.home_dir
    if workspace is None:
        raise click.ClickException("Workspace could not be resolved")

    final_model = model_id or settings.embedding_model
    region_selection = resolve_region(region, existing_hf_endpoint=settings.hf_endpoint if region == "auto" else None)
    update_config_field("hf_endpoint", region_selection.hf_endpoint or "null", config_path)

    if model_id:
        update_config_field("embedding_provider", "local", config_path)
        update_config_field("embedding_model", final_model, config_path)
        if final_model in MODEL_DIMS:
            update_config_field("embedding_dim", str(MODEL_DIMS[final_model]), config_path)

    source = region_selection.hf_endpoint or "HuggingFace official"
    console.print(f"Downloading [cyan]{final_model}[/] from {source}...")
    try:
        path = prefetch_model(final_model, workspace, hf_endpoint=region_selection.hf_endpoint)
        dimension = _verify_model(final_model, hf_endpoint=region_selection.hf_endpoint)
        update_config_field("embedding_dim", str(dimension), config_path)
    except Exception as exc:
        raise click.ClickException(f"Model download failed: {exc}") from exc
    console.print(f"[green]Model ready:[/] {path}")
    console.print(f"[green]Embedding verified:[/] dim={dimension}")


def _infer_language_strategy(model_id: str) -> str:
    if model_id == "BAAI/bge-large-en-v1.5":
        return "en"
    if model_id == "BAAI/bge-m3":
        return "zh/multi"
    if model_id in {"all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2"}:
        return "fast"
    return "custom"


def _verify_model(model_id: str, hf_endpoint: str | None) -> int:
    import asyncio

    from hippocampus.embedding.local import LocalEmbedder

    embedder = LocalEmbedder(model_id, hf_endpoint=hf_endpoint)
    asyncio.run(embedder.embed("hippocampus model prefetch verification"))
    return embedder.dimension
