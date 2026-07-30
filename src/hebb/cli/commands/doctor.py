"""hebb doctor — diagnose local installation health."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from hebb.config.loader import find_config_file, load_settings
from hebb.config.settings import Settings
from hebb.embedding.local import is_ml_stack_present, is_model_cached

console = Console()


@click.command("doctor")
def doctor_cmd() -> None:
    """Check local Hebb Mind setup and integration health."""
    table = Table(title="Hebb Mind Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    _add_python_check(table)
    settings = _add_config_check(table)
    _add_static_check(table)
    if settings is not None:
        _add_local_stack_check(table, settings)
        _add_model_check(table, settings)
        _add_service_check(table, settings)
    _add_cli_check(table, "claude", ["claude", "mcp", "list"])
    _add_cli_check(table, "codex", ["codex", "mcp", "list"])

    console.print(table)


def _add_python_check(table: Table) -> None:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 10)
    table.add_row("Python", _status(ok), version)


def _add_config_check(table: Table) -> Settings | None:
    config_path = find_config_file()
    if not config_path:
        table.add_row("Config", _status(False), "No hebb.json found. Run: hebb setup")
        return None

    settings = load_settings(config_path)
    table.add_row("Config", _status(True), str(config_path))
    table.add_row("Workspace", _status(settings.home_dir is not None), str(settings.home_dir))
    # Consolidation gates on llm_model (the actual driver of LLM calls), not
    # llm_api_key: a local/proxy model needs no key, while a set key without a
    # model still cannot consolidate.
    if not settings.llm_model:
        table.add_row("LLM", "[WARN]", "Not configured. Consolidation is disabled until llm_model is set.")
    else:
        table.add_row("LLM", "[OK]", settings.llm_model)
    return settings


def _add_static_check(table: Table) -> None:
    static_index = Path(__file__).resolve().parents[2] / "static" / "index.html"
    table.add_row("Web Console", _status(static_index.is_file()), str(static_index))


def _add_model_check(table: Table, settings: Settings) -> None:
    if not settings.embedding_enabled:
        table.add_row("Embedding", "[WARN]", "Disabled by config")
        return
    cached = is_model_cached(settings.embedding_model)
    detail = f"{settings.embedding_model} dim={settings.embedding_dim}"
    if not cached:
        detail += ". Run: hebb model prefetch"
    table.add_row("Embedding", _status(cached), detail)


def _add_local_stack_check(table: Table, settings: Settings) -> None:
    """Diagnose a configured local provider whose ML stack is not installed.

    A lean install (no ``local`` extra) silently degrades to ``NoopEmbedder`` /
    disabled rerank. Surface that loudly here with an actionable install hint,
    ahead of the model-cache check — otherwise a missing stack makes
    ``is_model_cached`` report "model not cached — run hebb model prefetch",
    which then hard-fails on the unguarded huggingface_hub import.

    The presence test is shared with ``hebb setup`` via
    :func:`hebb.embedding.local.is_ml_stack_present` so the two CLI commands
    can never disagree on what counts as an importable stack.
    """
    needs_stack = (
        (settings.embedding_enabled and settings.embedding_provider == "local")
        or (settings.rerank_enabled and settings.rerank_provider == "local")
    )
    if not needs_stack:
        return  # API-only / disabled configs never need the local stack.

    if is_ml_stack_present():
        table.add_row("ML stack", _status(True), "sentence-transformers importable")
    else:
        # Escape the hint — rich would otherwise eat ``[local]`` as a markup tag
        # and the user would see ``pip install hebb-mind`` (missing the extra).
        table.add_row(
            "ML stack",
            _status(False),
            escape(
                "Local provider configured but sentence-transformers is missing. "
                "Run: hebb setup  (or pip install hebb-mind[local])"
            ),
        )


def _add_service_check(table: Table, settings: Settings) -> None:
    host = "127.0.0.1" if settings.host in ("0.0.0.0", "") else settings.host
    url = f"http://{host}:{settings.port}"
    try:
        httpx.get(f"{url}/health", timeout=2)
        table.add_row("Service", "[OK]", url)
        _add_service_manager_check(table, installed_expected=True)
    except Exception:
        table.add_row("Service", "[WARN]", f"Not running at {url}. Run: hebb service install")
        _add_service_manager_check(table, installed_expected=False)


def _add_service_manager_check(table: Table, *, installed_expected: bool) -> None:
    """Verify the OS service manager is registered, so the server survives reboot."""
    try:
        from hebb.utils.service_manager import UnsupportedPlatformError, get_manager

        manager = get_manager()
        status = manager.status()
    except UnsupportedPlatformError as exc:
        table.add_row("Auto-start", "[WARN]", str(exc))
        return
    except Exception as exc:  # pragma: no cover — defensive
        table.add_row("Auto-start", "[WARN]", f"Could not query service manager: {exc}")
        return

    label = manager.display_name
    if status.installed:
        if status.running:
            table.add_row("Auto-start", "[OK]", f"{label} (running)")
        else:
            table.add_row("Auto-start", "[WARN]", f"{label} installed but not running. Run: hebb service start")
    else:
        table.add_row("Auto-start", "[WARN]", f"{label}: not installed. Run: hebb service install")


def _add_cli_check(table: Table, name: str, command: list[str]) -> None:
    if not shutil.which(name):
        table.add_row(f"{name} MCP", "[WARN]", f"{name} CLI not found")
        return
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except Exception as exc:
        table.add_row(f"{name} MCP", "[WARN]", str(exc))
        return
    status = "[OK]" if result.returncode == 0 and "hebb" in result.stdout else "[WARN]"
    install_cmd = "hebb claude-code install --scope user" if name == "claude" else "hebb codex install"
    detail = "hebb configured" if status == "[OK]" else f"Run: {install_cmd}"
    table.add_row(f"{name} MCP", status, detail)


def _status(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"
