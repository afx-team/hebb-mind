"""hebb setup — prepare the default out-of-box environment."""

from __future__ import annotations

from pathlib import Path

import click
from click.core import ParameterSource
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

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
from hebb.embedding.local import is_ml_stack_present

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
        _ensure_ml_stack(console)
        if workspace_model_available(workspace, model_id):
            console.print(f"[green]Model already present:[/] {model_cache_dir(workspace, model_id)}")
        else:
            model_path = _prefetch_with_progress(
                model_id,
                workspace,
                hf_endpoint=region_selection.hf_endpoint,
            )
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


def _prefetch_with_progress(model_id: str, workspace: Path, *, hf_endpoint: str | None) -> Path:
    """Download one model while rendering live terminal byte progress.

    Args:
        model_id: HuggingFace repository ID of the model to download.
        workspace: Resolved Hebb Mind workspace directory.
        hf_endpoint: Optional HuggingFace-compatible endpoint.

    Returns:
        Local directory containing the downloaded model.

    Raises:
        Exception: Propagates download failures from :func:`prefetch_model`.
    """
    size_hint = _download_tier_hint(model_id)
    columns = (
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )
    with Progress(*columns, console=console, transient=False) as progress:
        task_id = progress.add_task(
            f"[cyan]Downloading embedding model[/] [dim]({size_hint})[/]",
            total=None,
        )

        def update_progress(bytes_done: int, bytes_total: int, current_file: str) -> None:
            if _is_file_count_progress(current_file):
                return
            description = current_file.strip() or "Downloading embedding model"
            progress.update(
                task_id,
                description=f"[cyan]{description}[/] [dim]({size_hint})[/]",
                completed=bytes_done,
                total=bytes_total or None,
            )

        return prefetch_model(
            model_id,
            workspace,
            hf_endpoint=hf_endpoint,
            progress_callback=update_progress,
            suppress_native_progress=True,
        )


def _is_file_count_progress(description: str) -> bool:
    """Return whether a HuggingFace tqdm event counts files rather than bytes.

    Args:
        description: Description emitted by the HuggingFace tqdm instance.

    Returns:
        ``True`` for the snapshot-level ``Fetching N files`` counter.
    """
    normalized = description.strip().lower()
    return normalized.startswith("fetching ") and normalized.endswith(" files")


def _persist_region(hf_endpoint: str | None, config_path: Path) -> None:
    update_config_field("hf_endpoint", hf_endpoint or "null", config_path)


def _verify_model(model_id: str, hf_endpoint: str | None) -> int:
    import asyncio

    from hebb.embedding.local import LocalEmbedder

    embedder = LocalEmbedder(model_id, hf_endpoint=hf_endpoint)
    asyncio.run(embedder.embed("hebb setup verification"))
    return embedder.dimension


def _build_ml_stack_argv(
    method: str,
    *,
    use_cpu_torch: bool,
    mirror: str | None,
) -> tuple[list[str], dict[str, str]]:
    """Build the install command for the local ML stack (``sentence-transformers``).

    Installs the dependency directly (NOT ``hebb-mind[local]``) so editable /
    pipx installs are not re-fetched from PyPI and clobbered. On non-macOS the
    CPU-only torch wheel is preferred via the PyTorch CPU index (~250 MB vs
    ~2.5 GB CUDA); macOS PyPI wheels are already CPU-only, so the extra index is
    omitted there.

    Args:
        method: Install method — ``pip`` / ``pipx`` / ``editable`` (all use the
            venv's pip) or ``uv-tool`` (no pip; uses ``uv pip install``).
        use_cpu_torch: Whether to add the PyTorch CPU extra index-url.
        mirror: Optional PyPI mirror (``HEBB_PYPI_INDEX_URL``).

    Returns:
        ``(argv, env_overlay)`` — the command and extra env for ``subprocess.run``.

    Raises:
        click.ClickException: For a ``uv-tool`` install with ``uv`` missing.
    """
    import shutil
    import sys

    requirement = "sentence-transformers>=3.0.0"
    cpu_index = "https://download.pytorch.org/whl/cpu"
    env: dict[str, str] = {}

    if method == "uv-tool":
        uv = shutil.which("uv")
        if not uv:
            raise click.ClickException(
                "The local ML stack is missing and this is a uv-tool install "
                "without `uv` on PATH. Run "
                "`uv pip install --python <this-env> 'sentence-transformers>=3.0.0'` "
                "manually (or add uv to PATH and re-run `hebb setup`)."
            )
        argv: list[str] = [uv, "pip", "install", "--python", sys.executable, requirement]
        if use_cpu_torch:
            argv += ["--extra-index-url", cpu_index]
        if mirror:
            env["UV_INDEX_URL"] = mirror
    else:  # pip / pipx (pipx venvs ship pip) / editable venv — all have pip
        argv = [sys.executable, "-m", "pip", "install", requirement, "--progress-bar=on"]
        if use_cpu_torch:
            argv += ["--extra-index-url", cpu_index]
        if mirror:
            env["PIP_INDEX_URL"] = mirror

    return argv, env


def _ensure_ml_stack(console: Console) -> None:
    """Ensure the local ML stack (sentence-transformers + torch) is importable.

    A default ``pip install hebb-mind`` is lean by design — the heavy stack
    lives in the optional ``local`` extra. ``hebb setup`` always ends at
    ``_verify_model`` → ``LocalEmbedder``, which needs that stack, so install it
    on demand into the current environment: pip / pipx / editable venvs use the
    venv interpreter's pip; uv-tool venvs (no pip) use ``uv pip install``;
    system-managed Python is refused. This is the User Path Ownership hook —
    the framework installs exactly what the chosen config needs, across every
    install method.

    Raises:
        click.ClickException: If the stack is missing and installation fails or
            is refused. The caller invokes us inside its try block, so raising
            here preserves the install-F8 rule (no ``embedding_provider=local``
            is persisted on failure) and surfaces a single CLI error.
    """
    import importlib
    import os
    import subprocess
    import sys

    if is_ml_stack_present():
        return  # Stack already importable — nothing to do.

    from hebb.upgrade.installer import _classify_executable, _is_system_python

    # Refuse a system-managed interpreter BEFORE printing the install banner,
    # so the user doesn't see "Installing local ML stack" right before a hard
    # refusal that never attempts the install.
    if _is_system_python():
        raise click.ClickException(
            "The local ML stack is missing and this is a system-managed Python, "
            "which Hebb Mind will not modify. Create a virtualenv first, then run "
            "`hebb setup` (or `pip install hebb-mind[local]`)."
        )

    console.print(
        "[cyan]Installing local ML stack[/] [dim](sentence-transformers + CPU torch)[/]"
    )

    method = _classify_executable()  # pipx / uv-tool / pip
    use_cpu_torch = sys.platform != "darwin"
    mirror = os.environ.get("HEBB_PYPI_INDEX_URL")
    argv, env_overlay = _build_ml_stack_argv(method, use_cpu_torch=use_cpu_torch, mirror=mirror)
    env = {**os.environ, **env_overlay}

    try:
        # Inherit stdout/stderr so pip's native progress bar renders live.
        subprocess.run(argv, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(
            f"Failed to install the local ML stack (pip exited {exc.returncode}). "
            "Install it manually: `pip install 'sentence-transformers>=3.0.0'` "
            "(on Linux, add `--extra-index-url https://download.pytorch.org/whl/cpu`), "
            "or set a mirror via HEBB_PYPI_INDEX_URL, then re-run `hebb setup`."
        ) from exc

    # pip just installed sentence-transformers + torch into this interpreter's
    # site-packages, but the import system's FileFinder cached the pre-install
    # directory listing at process start. _verify_model imports
    # sentence_transformers in this same process immediately after, so
    # invalidate the cache or the stale finder can make the just-installed
    # package look missing (ModuleNotFoundError despite a successful install).
    importlib.invalidate_caches()
