"""hippocampus doctor — diagnose local installation health."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from hippocampus.config.loader import find_config_file, load_settings
from hippocampus.embedding.local import is_model_cached

console = Console()


@click.command("doctor")
def doctor_cmd() -> None:
    """Check local Hippocampus setup and integration health."""
    table = Table(title="Hippocampus Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    _add_python_check(table)
    settings = _add_config_check(table)
    _add_static_check(table)
    if settings is not None:
        _add_model_check(table, settings)
        _add_service_check(table, settings)
    _add_cli_check(table, "claude", ["claude", "mcp", "list"])
    _add_cli_check(table, "codex", ["codex", "mcp", "list"])

    console.print(table)


def _add_python_check(table: Table) -> None:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 10)
    table.add_row("Python", _status(ok), version)


def _add_config_check(table: Table):
    config_path = find_config_file()
    if not config_path:
        table.add_row("Config", _status(False), "No hippocampus.json found. Run: hippocampus setup")
        return None

    settings = load_settings(config_path)
    table.add_row("Config", _status(True), str(config_path))
    table.add_row("Workspace", _status(settings.home_dir is not None), str(settings.home_dir))
    if not settings.llm_api_key:
        table.add_row("LLM", "[WARN]", "Not configured. Consolidation is disabled until llm_api_key is set.")
    else:
        table.add_row("LLM", "[OK]", settings.llm_model or "configured")
    return settings


def _add_static_check(table: Table) -> None:
    static_index = Path(__file__).resolve().parents[2] / "static" / "index.html"
    table.add_row("Web Console", _status(static_index.is_file()), str(static_index))


def _add_model_check(table: Table, settings) -> None:
    if not settings.embedding_enabled:
        table.add_row("Embedding", "[WARN]", "Disabled by config")
        return
    cached = is_model_cached(settings.embedding_model)
    detail = f"{settings.embedding_model} dim={settings.embedding_dim}"
    if not cached:
        detail += ". Run: hippocampus model prefetch"
    table.add_row("Embedding", _status(cached), detail)


def _add_service_check(table: Table, settings) -> None:
    host = "127.0.0.1" if settings.host in ("0.0.0.0", "") else settings.host
    url = f"http://{host}:{settings.port}"
    try:
        httpx.get(f"{url}/health", timeout=2)
        table.add_row("Service", "[OK]", url)
    except Exception:
        table.add_row("Service", "[WARN]", f"Not running at {url}. Run: hippocampus start")


def _add_cli_check(table: Table, name: str, command: list[str]) -> None:
    if not shutil.which(name):
        table.add_row(f"{name} MCP", "[WARN]", f"{name} CLI not found")
        return
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except Exception as exc:
        table.add_row(f"{name} MCP", "[WARN]", str(exc))
        return
    status = "[OK]" if result.returncode == 0 and "hippocampus" in result.stdout else "[WARN]"
    install_cmd = (
        "hippocampus cc install --scope user" if name == "claude" else "hippocampus codex install --scope user"
    )
    detail = "hippocampus configured" if status == "[OK]" else f"Run: {install_cmd}"
    table.add_row(f"{name} MCP", status, detail)


def _status(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"
