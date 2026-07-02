"""hebb agent-sync — sync Codex and Claude Code sessions through Hebb Mind."""

from __future__ import annotations

import json
from typing import Any

import click
import httpx
from rich.console import Console
from rich.table import Table

from hebb.cli._url import resolve_server_url

console = Console()

_HOST_CHOICES = ["claude-code", "codex"]


@click.group("agent-sync")
def agent_sync_cmd() -> None:
    """Collect agent sessions and sync them into Hebb Mind."""


@agent_sync_cmd.command("list")
@click.option("--host", type=click.Choice(_HOST_CHOICES), default=None, help="Filter by source software.")
@click.option("--url", default=None, hidden=True)
@click.option("--json", "as_json", is_flag=True, hidden=True)
def list_cmd(host: str | None, url: str | None, as_json: bool) -> None:
    """List local Codex and Claude Code sessions with sync status."""
    url = url or resolve_server_url()
    try:
        sessions = _get_sessions(url, host=_api_host(host))
    except httpx.HTTPError as exc:
        _fail_request(url, exc)
    if as_json:
        console.print_json(json.dumps(sessions))
        return
    _print_sessions(sessions)


@agent_sync_cmd.command("sync")
@click.option("--host", type=click.Choice(_HOST_CHOICES), default=None, help="Sync only one source software.")
@click.option("--dry-run", is_flag=True, help="Scan and report without writing memories.")
@click.option("--url", default=None, hidden=True)
@click.option("--json", "as_json", is_flag=True, hidden=True)
def sync_cmd(host: str | None, dry_run: bool, url: str | None, as_json: bool) -> None:
    """Sync pending agent-session turns into Hebb Mind."""
    url = url or resolve_server_url()
    payload: dict[str, object] = {"host": _api_host(host), "dry_run": dry_run}
    try:
        result = _post_sync(url, payload)
    except httpx.HTTPError as exc:
        _fail_request(url, exc)
    if as_json:
        console.print_json(json.dumps(result))
        return
    _print_sync_result(result)


def _api_host(host: str | None) -> str | None:
    """Translate CLI host spelling to the API value.

    Args:
        host: CLI host option value.

    Returns:
        API host value, or ``None`` for all supported agents.
    """
    if host is None:
        return None
    if host == "claude-code":
        return "claude_code"
    return host


def _get_sessions(url: str, *, host: str | None) -> list[dict[str, Any]]:
    """Fetch agent sessions from the Hebb Mind daemon.

    Args:
        url: Base server URL.
        host: Optional API host filter.

    Returns:
        Session dictionaries returned by the daemon.

    Raises:
        httpx.HTTPError: If the daemon request fails.
    """
    params: dict[str, str] = {}
    if host:
        params["host"] = host
    resp = httpx.get(f"{url}/api/v1/agent-sync/sessions", params=params, timeout=10)
    resp.raise_for_status()
    return list(resp.json())


def _post_sync(url: str, payload: dict[str, object]) -> dict[str, Any]:
    """Post an agent-session sync request to the Hebb Mind daemon.

    Args:
        url: Base server URL.
        payload: Request body accepted by ``/api/v1/agent-sync/sync``.

    Returns:
        Sync result dictionary returned by the daemon.

    Raises:
        httpx.HTTPError: If the daemon request fails.
    """
    resp = httpx.post(f"{url}/api/v1/agent-sync/sync", json=payload, timeout=120)
    resp.raise_for_status()
    return dict(resp.json())


def _print_sessions(sessions: list[dict[str, Any]]) -> None:
    """Render agent sessions as a CLI table.

    Args:
        sessions: Session dictionaries returned by the daemon.

    Returns:
        None.
    """
    if not sessions:
        console.print("[yellow]No local Codex or Claude Code sessions found.[/]")
        return

    table = Table(title="Agent Sync Sessions")
    table.add_column("Agent")
    table.add_column("Project")
    table.add_column("Synced")
    table.add_column("Pending")
    table.add_column("Updated")
    table.add_column("Session ID")
    for session in sessions:
        turn_count = int(session.get("turn_count") or 0)
        synced = int(session.get("synced_turns") or 0)
        pending = int(session.get("unsynced_turns") or 0)
        table.add_row(
            _host_label(str(session.get("host") or "")),
            str(session.get("project") or "-"),
            f"{synced}/{turn_count}",
            str(pending),
            str(session.get("latest_timestamp") or session.get("updated_at") or "-"),
            str(session.get("id") or "-"),
        )
    console.print(table)


def _print_sync_result(result: dict[str, Any]) -> None:
    """Render the agent-sync write result.

    Args:
        result: Sync response returned by the daemon.

    Returns:
        None.
    """
    dry_run = bool(result.get("dry_run"))
    prefix = "[cyan]Dry run:[/]" if dry_run else "[green]Synced:[/]"
    console.print(
        f"{prefix} {result.get('sessions_scanned', 0)} sessions, "
        f"{result.get('turns_found', 0)} turns, "
        f"{result.get('memories_created', 0)} created, "
        f"{result.get('skipped_existing', 0)} skipped, "
        f"{result.get('failed', 0)} failed"
    )

    items = list(result.get("items") or [])
    if not items:
        return
    table = Table(title="Sync Items")
    table.add_column("Agent")
    table.add_column("Project")
    table.add_column("Turns")
    table.add_column("Created")
    table.add_column("Skipped")
    table.add_column("Failed")
    for item in items:
        table.add_row(
            _host_label(str(item.get("host") or "")),
            str(item.get("project") or "-"),
            str(item.get("turns_found") or 0),
            str(item.get("memories_created") or 0),
            str(item.get("skipped_existing") or 0),
            str(item.get("failed") or 0),
        )
    console.print(table)


def _host_label(host: str) -> str:
    """Return the user-facing host label.

    Args:
        host: API host id.

    Returns:
        Human-readable host label.
    """
    return "Claude Code" if host == "claude_code" else "Codex" if host == "codex" else host


def _fail_request(url: str, exc: httpx.HTTPError) -> None:
    """Print a consistent daemon failure and exit.

    Args:
        url: Base server URL that failed.
        exc: HTTPX exception raised by the request.

    Raises:
        SystemExit: Always exits with status 1.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        console.print(f"[red]Agent Sync API failed at {url}[/] (HTTP {status})")
        if status in (404, 405):
            console.print("  The running Hebb Mind service may be older than this checkout.")
            console.print("  Restart the Hebb Mind service so CLI and server use the same version.")
        else:
            console.print(f"  {exc}")
    else:
        console.print(f"[red]Cannot reach {url}[/]")
        console.print(f"  {exc}")
        console.print("  Install/start the background service: [cyan]hebb service install[/]")
    raise SystemExit(1)
