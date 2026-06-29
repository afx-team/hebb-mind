"""hebb setup — prepare the default out-of-box environment."""

from __future__ import annotations

from pathlib import Path

import click
from click.core import ParameterSource
from rich.console import Console

from hebb.config.init import default_init_target, initialize_workspace
from hebb.config.loader import find_config_file, load_settings, update_config_field
from hebb.embedding.catalog import (
    LANGUAGE_CHOICES,
    LEGACY_DEFAULT_MODELS,
    PROFILE_CHOICES,
    REGION_CHOICES,
    choose_model,
    model_cache_dir,
    prefetch_model,
    resolve_language,
    resolve_region,
    workspace_model_available,
)

console = Console()


@click.command("setup")
@click.option("--language", type=click.Choice(LANGUAGE_CHOICES), default="auto", show_default=True)
@click.option("--region", type=click.Choice(REGION_CHOICES), default="auto", show_default=True)
@click.option("--profile", type=click.Choice(PROFILE_CHOICES), default="default", show_default=True)
@click.pass_context
def setup_cmd(ctx: click.Context, language: str, region: str, profile: str) -> None:
    """Prepare Hebb Mind for first use without starting the service."""
    config_path = _ensure_initialized()
    settings = load_settings(config_path)

    language_selection = resolve_language(language)
    language_explicit = ctx.get_parameter_source("language") == ParameterSource.COMMANDLINE
    profile_explicit = ctx.get_parameter_source("profile") == ParameterSource.COMMANDLINE

    # Decide the target model WITHOUT persisting it yet — a failed download must
    # not leave hebb.json pointing at an unusable model (install F8).
    should_select_model = _should_select_model(settings.embedding_model, language_explicit, profile_explicit)
    if should_select_model:
        spec = choose_model(language_selection.language, profile)
        model_id = spec.model_id
        console.print(f"[green]Selected embedding model:[/] {model_id} ({language_selection.language}, {profile})")
    else:
        model_id = settings.embedding_model
        console.print(f"[yellow]Keeping existing embedding model:[/] {model_id}")

    region_selection = resolve_region(region, existing_hf_endpoint=settings.hf_endpoint if region == "auto" else None)
    _persist_region(region_selection.hf_endpoint, config_path)

    if region_selection.message:
        console.print(f"[yellow]{region_selection.message}[/]")
    source = region_selection.hf_endpoint or "HuggingFace official"
    console.print(f"[green]Download source:[/] {source} ({region_selection.region})")

    workspace = settings.home_dir
    if workspace is None:
        raise click.ClickException("Workspace could not be resolved")

    # Prefetch + verify FIRST; only persist the embedding config after success so
    # a retry self-heals and the prior (working) config is left untouched on failure.
    # An already-cached model is reused — never re-download (and never pull a
    # multi-GB tier just to confirm it is present).
    try:
        if workspace_model_available(workspace, model_id):
            console.print(f"[green]Model already present:[/] {model_cache_dir(workspace, model_id)}")
        else:
            console.print(f"[cyan]Downloading embedding model[/] ({_download_tier_hint(model_id)})...")
            model_path = prefetch_model(model_id, workspace, hf_endpoint=region_selection.hf_endpoint)
            console.print(f"[green]Model ready:[/] {model_path}")
        dimension = _verify_model(model_id, hf_endpoint=region_selection.hf_endpoint)
        console.print(f"[green]Embedding verified:[/] dim={dimension}")
    except Exception as exc:
        raise click.ClickException(f"Model setup failed: {exc}") from exc

    if should_select_model:
        update_config_field("embedding_provider", "local", config_path)
        update_config_field("embedding_model", model_id, config_path)
    # Always persist the verified dimension (matches the live embedder).
    update_config_field("embedding_dim", str(dimension), config_path)

    console.print()
    console.print("[bold]Hebb Mind setup complete.[/]")
    console.print("Next steps:")
    console.print("  Install background service: [cyan]hebb service install[/]")
    console.print("  Open Web Console:           [cyan]hebb console[/]")
    console.print("  Claude Code setup:          [cyan]hebb claude-code install --scope user[/]")
    console.print("  Codex project setup:        [cyan]hebb codex install[/]")
    console.print("  Check health:               [cyan]hebb doctor[/]")


def _ensure_initialized() -> Path:
    config_path = find_config_file()
    if config_path:
        console.print(f"[green]Using config:[/] {config_path}")
        return config_path

    target = default_init_target()
    result = initialize_workspace(target, force=False)
    console.print(f"[green]Initialized workspace:[/] {target}")
    return result.settings_path


def _should_select_model(current_model: str | None, language_explicit: bool, profile_explicit: bool) -> bool:
    if language_explicit or profile_explicit:
        return True
    if not current_model:
        return True
    return current_model in LEGACY_DEFAULT_MODELS


def _download_tier_hint(model_id: str) -> str:
    """Return a human-readable size estimate for a model download.

    Args:
        model_id: HuggingFace repository ID of the model to be downloaded.

    Returns:
        A short tier label such as ``small ~90MB`` for use in setup output.
    """
    if model_id in {"all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2"}:
        return "small ~90MB"
    if model_id == "intfloat/multilingual-e5-small":
        return "multilingual ~470MB"
    if model_id in {"BAAI/bge-large-en-v1.5", "BAAI/bge-m3"}:
        return "best 1-2GB"
    return "size varies"


def _persist_region(hf_endpoint: str | None, config_path: Path) -> None:
    update_config_field("hf_endpoint", hf_endpoint or "null", config_path)


def _verify_model(model_id: str, hf_endpoint: str | None) -> int:
    import asyncio

    from hebb.embedding.local import LocalEmbedder

    embedder = LocalEmbedder(model_id, hf_endpoint=hf_endpoint)
    asyncio.run(embedder.embed("hebb setup verification"))
    return embedder.dimension
