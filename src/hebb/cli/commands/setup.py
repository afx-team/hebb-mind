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
    prefetch_model,
    resolve_language,
    resolve_region,
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

    should_select_model = _should_select_model(settings.embedding_model, language_explicit, profile_explicit)
    if should_select_model:
        spec = choose_model(language_selection.language, profile)
        update_config_field("embedding_provider", "local", config_path)
        update_config_field("embedding_model", spec.model_id, config_path)
        update_config_field("embedding_dim", str(spec.dimension), config_path)
        model_id = spec.model_id
        console.print(f"[green]Selected embedding model:[/] {model_id} ({language_selection.language}, {profile})")
    else:
        model_id = settings.embedding_model
        console.print(f"[yellow]Keeping existing embedding model:[/] {model_id}")

    settings = load_settings(config_path)
    region_selection = resolve_region(region, existing_hf_endpoint=settings.hf_endpoint if region == "auto" else None)
    _persist_region(region_selection.hf_endpoint, config_path)

    if region_selection.message:
        console.print(f"[yellow]{region_selection.message}[/]")
    source = region_selection.hf_endpoint or "HuggingFace official"
    console.print(f"[green]Download source:[/] {source} ({region_selection.region})")

    workspace = settings.home_dir
    if workspace is None:
        raise click.ClickException("Workspace could not be resolved")

    try:
        model_path = prefetch_model(model_id, workspace, hf_endpoint=region_selection.hf_endpoint)
        console.print(f"[green]Model ready:[/] {model_path}")
        dimension = _verify_model(model_id, hf_endpoint=region_selection.hf_endpoint)
        update_config_field("embedding_dim", str(dimension), config_path)
        console.print(f"[green]Embedding verified:[/] dim={dimension}")
    except Exception as exc:
        raise click.ClickException(f"Model setup failed: {exc}") from exc

    console.print()
    console.print("[bold]Hebb Mind setup complete.[/]")
    console.print("Next steps:")
    console.print("  Install background service: [cyan]hebb service install[/]")
    console.print("  Open Web Console:           [cyan]hebb console[/]")
    console.print("  Claude Code setup:          [cyan]hebb claude-code install --scope user[/]")
    console.print("  Codex setup:                [cyan]hebb codex install --scope user[/]")
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


def _persist_region(hf_endpoint: str | None, config_path: Path) -> None:
    update_config_field("hf_endpoint", hf_endpoint or "null", config_path)


def _verify_model(model_id: str, hf_endpoint: str | None) -> int:
    import asyncio

    from hebb.embedding.local import LocalEmbedder

    embedder = LocalEmbedder(model_id, hf_endpoint=hf_endpoint)
    asyncio.run(embedder.embed("hebb setup verification"))
    return embedder.dimension
