"""hebb upgrade — check for and apply Hebb Mind updates from the CLI.

For users who don't use the web console (headless servers, ssh, CI). When the
daemon is running it drives the upgrade through the daemon's ``/upgrade``
endpoints (so two upgraders never race); when the daemon is unreachable it
shells out to the detached helper directly.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import click
import httpx
from rich.console import Console

from hebb.cli._url import resolve_server_url

console = Console()


def _daemon_state(url: str) -> dict | None:
    """Return the daemon's upgrade state, or None if it is unreachable."""
    try:
        resp = httpx.get(f"{url}/api/v1/admin/upgrade", timeout=3)
        resp.raise_for_status()
        return dict(resp.json())
    except Exception:
        return None


def _print_status(state: dict) -> None:
    current = state.get("current_version") or "?"
    latest = state.get("latest_version") or "?"
    if state.get("available"):
        console.print(f"[bold]Update available:[/bold] {current} → [green]{latest}[/green]")
    else:
        console.print(f"[bold]Up to date[/bold] (current {current}, latest {latest})")
    if state.get("last_check_error"):
        console.print(f"[yellow]Last check error:[/yellow] {state['last_check_error']}")
    if not state.get("auto_upgradable", True) and state.get("refusal_reason"):
        console.print(f"[yellow]Manual upgrade required:[/yellow] {state['refusal_reason']}")
    last = state.get("last_upgrade")
    if last:
        console.print(
            f"Last upgrade: {last.get('from_version')} → {last.get('to_version')} "
            f"({last.get('status')}, {last.get('method')})"
        )


def _apply_via_daemon(url: str) -> int:
    """POST /apply and poll until the upgrade finishes. Returns an exit code."""
    try:
        resp = httpx.post(f"{url}/api/v1/admin/upgrade/apply", timeout=10)
    except Exception as exc:
        console.print(f"[red]Failed to reach daemon:[/red] {exc}")
        return 1
    if resp.status_code == 409:
        console.print(f"[yellow]Refused:[/yellow] {resp.json().get('detail')}")
        return 1
    if resp.status_code != 200:
        console.print(f"[red]Apply failed ({resp.status_code}):[/red] {resp.text}")
        return 1

    console.print("Upgrade started — the service is restarting…")
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(2)
        state = _daemon_state(url)
        if state is None:
            continue  # daemon mid-restart
        if not state.get("upgrade_in_progress"):
            last = state.get("last_upgrade") or {}
            if last.get("status") == "success":
                console.print(f"[green]Upgraded to {last.get('to_version')}[/green]")
                return 0
            console.print(f"[red]Upgrade failed:[/red] {last.get('log_tail') or last.get('status')}")
            return 1
    console.print("[yellow]Timed out waiting for the upgrade to finish. Run 'hebb status'.[/yellow]")
    return 1


def _apply_via_helper() -> int:
    """Run the detached helper synchronously (daemon not running)."""
    from hebb.config.loader import load_settings
    from hebb.upgrade.installer import build_command

    settings = load_settings()
    cmd = build_command()
    if not cmd.auto_upgradable:
        console.print(f"[red]Cannot auto-upgrade:[/red] {cmd.refusal_reason}")
        return 1
    console.print(f"Upgrading hebb-mind via {cmd.method}…")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "hebb.upgrade.helper",
            "--method",
            cmd.method,
            "--grace",
            str(settings.upgrade_grace_seconds),
            "--home",
            str(settings.home_dir),
            "--port",
            str(settings.port),
        ]
    )
    return proc.returncode


@click.command("upgrade")
@click.option("--check", "check", is_flag=True, help="Force a PyPI check now and print the result.")
@click.option("--apply", "apply_", is_flag=True, help="Apply the available upgrade without prompting.")
@click.option("--status", "status_flag", is_flag=True, help="Print the raw upgrade state as JSON.")
def upgrade_cmd(check: bool, apply_: bool, status_flag: bool) -> None:
    """Check for and apply Hebb Mind updates."""
    url = resolve_server_url()

    if status_flag:
        state = _daemon_state(url)
        if state is not None:
            console.print_json(json.dumps(state))
            return
        from hebb.config.loader import load_settings
        from hebb.upgrade import state as upgrade_state

        settings = load_settings()
        assert settings.home_dir is not None
        payload = upgrade_state.load(settings.home_dir).model_dump(mode="json")
        console.print_json(json.dumps(payload))
        return

    if check:
        try:
            resp = httpx.post(f"{url}/api/v1/admin/upgrade/check", timeout=15)
            resp.raise_for_status()
            _print_status(resp.json())
        except Exception:
            # Daemon down — check directly.
            import asyncio

            from hebb.config.loader import load_settings
            from hebb.upgrade.checker import run_check

            settings = load_settings()
            assert settings.home_dir is not None
            checked = asyncio.run(run_check(settings.home_dir))
            _print_status(checked.model_dump(mode="json"))
        return

    if apply_:
        state = _daemon_state(url)
        raise SystemExit(_apply_via_daemon(url) if state is not None else _apply_via_helper())

    # Default: show status, prompt to apply when an upgrade is available.
    state = _daemon_state(url)
    if state is None:
        console.print("[yellow]Daemon not reachable.[/yellow] Run 'hebb upgrade --check' to check directly.")
        return
    _print_status(state)
    if state.get("available") and state.get("auto_upgradable", False):
        if click.confirm("Upgrade now?", default=False):
            raise SystemExit(_apply_via_daemon(url))
