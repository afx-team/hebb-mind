"""hebb config — view and modify hebb.json."""

from __future__ import annotations

import json

import click
from rich.console import Console
from rich.table import Table

from hebb.config.loader import find_config_file, load_settings, update_config_field
from hebb.config.settings import Settings
from hebb.config.workspace import resolve_workspace

console = Console()


@click.group("config")
def config_cmd() -> None:
    """View and modify hebb.json configuration."""
    pass


@config_cmd.command("list")
def config_list() -> None:
    """Show all current configuration values."""
    path = find_config_file()
    if not path:
        console.print("[red]No hebb.json found. Run `hebb setup` first.[/]")
        raise SystemExit(1)

    settings = load_settings(path)
    data = settings.model_dump(exclude={"home_dir"})

    workspace = resolve_workspace(path)
    table = Table(title=f"Configuration ({path})", show_lines=False)
    table.add_column("Key", style="cyan", min_width=30)
    table.add_column("Value", style="white")

    # Show workspace first
    table.add_row("workspace", str(workspace))

    for key, value in data.items():
        display = _mask(key, value)
        table.add_row(key, display)

    console.print(table)


@config_cmd.command("get")
@click.argument("key")
def config_get(key: str) -> None:
    """Get a single configuration value."""
    path = find_config_file()
    if not path:
        console.print("[red]No hebb.json found.[/]")
        raise SystemExit(1)

    settings = load_settings(path)

    # Allow reading computed properties
    if key == "workspace":
        console.print(str(settings.home_dir))
        return

    data = settings.model_dump()

    if key not in data:
        console.print(f"[red]Unknown key:[/] {key}")
        console.print(f"[dim]Available keys: {', '.join(sorted(data.keys()))}, workspace[/]")
        raise SystemExit(1)

    console.print(f"{key} = {_mask(key, data[key])}")


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value in hebb.json.

    Examples:

      hebb config set llm_api_key sk-xxx

      hebb config set llm_model openai/gpt-4o

      hebb config set port 8000

      hebb config set embedding_enabled false

      hebb config set home /data/hebb
    """
    try:
        path, _ = update_config_field(key, value)
        # Re-read to show the coerced value
        with open(path) as f:
            data = json.load(f)
        display = _mask(key, data[key])
        console.print(f"[green]Set[/] {key} = {display}")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        available = ", ".join(sorted(Settings.model_fields.keys()))
        console.print(f"[dim]Available keys: {available}[/]")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)


@config_cmd.command("path")
def config_path() -> None:
    """Show the resolved config file path."""
    path = find_config_file()
    if path:
        console.print(str(path))
    else:
        console.print("[yellow]No hebb.json found.[/]")
        raise SystemExit(1)


# Sensitive config keys masked by `hebb config list` / `get`. Kept in sync with
# the server side (server/routers/config.py SENSITIVE_KEYS): embedding_http_headers
# carries a bearer token and pg_url embeds a password.
_SENSITIVE_KEYS = ("llm_api_key", "pg_url", "embedding_api_key", "embedding_http_headers")


def _mask_pg_url(url: str) -> str:
    """Mask the password in a PostgreSQL URL, preserving the rest for diagnosis.

    Args:
        url: A connection URL, e.g. ``postgresql://user:secret@host:5432/db``.

    Returns:
        The URL with the password component replaced by ``****``. If the URL has
        no userinfo password, it is returned with the whole value masked.
    """
    # scheme://user:password@host/...  -> mask only the password segment.
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        userinfo, _, hostpart = rest.partition("@")
        if ":" in userinfo:
            user, _, _ = userinfo.partition(":")
            return f"{scheme}://{user}:****@{hostpart}"
    return "****"


def _mask(key: str, value: object) -> str:
    """Mask sensitive values for display.

    Args:
        key: The config key.
        value: The raw value.

    Returns:
        A display string with any secret hidden. Non-empty secrets are masked
        unconditionally (no length gate); pg_url keeps its non-secret parts.
    """
    if value is None:
        return "[dim]null[/]"
    s = str(value)
    if not s:
        return s
    if key == "pg_url":
        return _mask_pg_url(s)
    if key in _SENSITIVE_KEYS:
        return "****"
    return s
