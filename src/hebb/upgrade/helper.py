"""Detached upgrade worker — ``python -m hebb.upgrade.helper``.

Spawned by ``POST /api/v1/admin/upgrade/apply`` as a fully detached child
(``start_new_session`` / ``DETACHED_PROCESS``) so it survives the daemon's own
shutdown. It stops the OS service, runs the package upgrade, brings the service
back up, and verifies ``/health`` — writing every transition to
``upgrade_state.json`` so the console can surface progress and the final result.

The daemon cannot pip-install itself (files mapped into the running process),
so this work must happen in a separate, detached process. See
``reports/design/auto-upgrade.md``.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from hebb import __version__
from hebb.upgrade import state as upgrade_state
from hebb.upgrade.installer import Method, build_command
from hebb.upgrade.state import LastUpgrade, _pid_alive

logger = logging.getLogger(__name__)

INSTALL_TIMEOUT_SECONDS = 900
HEALTH_TIMEOUT_SECONDS = 60
LOG_TAIL_CHARS = 4000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _terminate_parent(pid: int, grace: float) -> None:
    """Ensure the parent daemon is gone: wait ``grace`` s, then SIGTERM/SIGKILL.

    Stopping the OS service already brings the daemon down; this confirms it and
    forces the issue if a stuck process is holding files we are about to
    overwrite. A non-positive / missing pid is a no-op (CLI-driven upgrade with
    no live daemon).
    """
    if pid <= 0:
        return
    deadline = time.time() + grace
    while time.time() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.5)
    # SIGKILL does not exist on Windows (signal module has only SIGTERM there);
    # referencing it would raise AttributeError before the loop even starts.
    signals = [signal.SIGTERM]
    if os.name != "nt" and hasattr(signal, "SIGKILL"):
        signals.append(signal.SIGKILL)
    for sig in signals:
        if not _pid_alive(pid):
            return
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            return
        time.sleep(2.0)


def _service_op(op: str) -> bool:
    """Run ``stop`` / ``start`` on the installed service across user+system scope.

    Returns True if the op ran on an installed service; False when no installed
    service exists in any scope (e.g. a bare ``hebb _serve``) OR the op raised.
    Callers that must distinguish "no service" from "op failed" use
    :func:`_service_installed`.
    """
    from hebb.utils.service_manager import (
        ServiceError,
        ServiceNotInstalledError,
        UnsupportedPlatformError,
        get_manager,
    )

    for scope in ("user", "system"):
        try:
            manager = get_manager(scope=scope)
            if not manager.status().installed:
                continue
            getattr(manager, op)()
            return True
        except ServiceNotInstalledError:
            continue
        except (ServiceError, UnsupportedPlatformError) as exc:
            logger.warning("service %s failed (scope=%s): %s", op, scope, exc)
            continue
        except Exception:
            logger.exception("service %s crashed (scope=%s)", op, scope)
            continue
    return False


def _service_installed() -> bool:
    """Return True if an OS service is registered in any scope.

    Distinguishes "no service to restart" (truly bare ``hebb _serve``) from
    "start failed", so a transient start failure is reported as a failed
    upgrade instead of being silently treated as a serviceless install.
    """
    from hebb.utils.service_manager import (
        ServiceError,
        UnsupportedPlatformError,
        get_manager,
    )

    for scope in ("user", "system"):
        try:
            if get_manager(scope=scope).status().installed:
                return True
        except (ServiceError, UnsupportedPlatformError):
            continue
        except Exception:
            logger.exception("service status check crashed (scope=%s)", scope)
            continue
    return False


def _installed_version() -> str | None:
    """Return the on-disk ``hebb`` version via a fresh interpreter.

    Run in a subprocess so the freshly-installed package is imported, not the
    stale module already loaded into this long-lived helper process.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", "import hebb; print(hebb.__version__)"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    out = proc.stdout.strip()
    return out or None


def _wait_health(port: int, timeout: int) -> bool:
    """Poll ``http://127.0.0.1:<port>/health`` until it answers or times out."""
    import httpx

    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/health"
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def run_upgrade(
    *,
    home_dir: Path,
    method: Method,
    parent_pid: int,
    grace: float,
    port: int,
    dry_run: bool = False,
) -> int:
    """Execute the full stop → upgrade → restart → verify flow.

    Returns a process exit code (0 on a successful upgrade, 1 otherwise). Every
    outcome — success or failure — is persisted to ``upgrade_state.json`` and
    the service is always brought back up in a ``finally`` so a crash never
    leaves the daemon down.
    """
    from_version = upgrade_state.load(home_dir).current_version or __version__
    target = upgrade_state.load(home_dir).latest_version

    cmd = build_command(method)
    if not cmd.auto_upgradable:
        upgrade_state.update(
            home_dir,
            upgrade_in_progress=False,
            last_upgrade=LastUpgrade(
                from_version=from_version,
                to_version=target or "",
                started_at=_now(),
                finished_at=_now(),
                status="failed",
                method=method,
                log_tail=cmd.refusal_reason or "install method is not auto-upgradable",
            ).model_dump(),
        )
        return 1

    started_at = _now()
    upgrade_state.update(
        home_dir,
        upgrade_in_progress=True,
        last_upgrade=LastUpgrade(
            from_version=from_version,
            to_version=target or "",
            started_at=started_at,
            status="in_progress",
            method=method,
        ).model_dump(),
    )

    status = "failed"
    log_tail = ""
    new_version = from_version

    try:
        if not dry_run:
            _service_op("stop")
            _terminate_parent(parent_pid, grace)
            returncode, log_tail = _run_install(cmd.argv, cmd.env)
        else:
            returncode, log_tail = 0, "[dry-run] upgrade skipped"

        if returncode == 0:
            detected = None if dry_run else _installed_version()
            new_version = detected or target or from_version
            status = "success"
        else:
            status = "failed"
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("Upgrade helper crashed")
        status = "failed"
        log_tail = f"{type(exc).__name__}: {exc}"
    finally:
        # Always attempt to bring the service back up — even on a failed upgrade
        # the old version is still installed and the daemon must not be left down.
        if not dry_run:
            if _service_installed():
                _service_op("start")
                if not _wait_health(port, HEALTH_TIMEOUT_SECONDS):
                    # Installed but did not come back healthy — a successful
                    # package install that leaves the daemon down is still a
                    # failed upgrade, not a silent success.
                    status = "failed"
                    log_tail = (log_tail + "\n" if log_tail else "") + (
                        "daemon did not return to healthy after upgrade"
                    )
            else:
                # No OS service to relaunch (bare ``hebb _serve``); the new
                # version loads on the next manual start.
                log_tail = (log_tail + "\n" if log_tail else "") + (
                    "service not installed — restart the daemon to load the new version"
                )

        final = upgrade_state.load(home_dir)
        final.upgrade_in_progress = False
        if status == "success":
            final.current_version = new_version
            final.available = bool(final.latest_version and final.latest_version != new_version)
        final.last_upgrade = LastUpgrade(
            from_version=from_version,
            to_version=new_version if status == "success" else (target or ""),
            started_at=started_at,
            finished_at=_now(),
            status=status,
            method=method,
            log_tail=(log_tail or None) if log_tail else None,
        )
        upgrade_state.save(home_dir, final)

    return 0 if status == "success" else 1


def _run_install(argv: list[str], extra_env: dict[str, str]) -> tuple[int, str]:
    """Run the upgrade subprocess, returning ``(returncode, log_tail)``."""
    env = {**os.environ, **extra_env}
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            env=env,
            timeout=INSTALL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return 1, f"upgrade timed out after {INSTALL_TIMEOUT_SECONDS}s"
    except FileNotFoundError as exc:
        return 1, f"upgrade command not found: {exc}"
    combined = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, combined[-LOG_TAIL_CHARS:]


def spawn_detached(
    *,
    home_dir: Path,
    port: int,
    grace: float,
    method: str,
    parent_pid: int,
) -> int:
    """Spawn the upgrade helper as a fully detached child and return its PID.

    Detached (new session / process group, closed fds) so it outlives the daemon
    it is about to stop. Shared by the ``/apply`` endpoint and the scheduler's
    auto-upgrade path.

    Args:
        home_dir: Workspace root the helper writes state into.
        port: Daemon port the helper polls for ``/health`` after restart.
        grace: Seconds to wait for the daemon to exit before forcing it.
        method: Detected install method (pip / pipx / uv-tool).
        parent_pid: PID of the daemon to wait on / terminate.

    Returns:
        The spawned helper's process id.
    """
    argv = [
        sys.executable,
        "-m",
        "hebb.upgrade.helper",
        "--parent-pid",
        str(parent_pid),
        "--method",
        str(method),
        "--grace",
        str(grace),
        "--home",
        str(home_dir),
        "--port",
        str(port),
    ]
    kwargs: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:  # Windows: detach from the parent console / process group.
        detached_process = 0x00000008
        create_new_process_group = 0x00000200
        kwargs["creationflags"] = detached_process | create_new_process_group
    proc = subprocess.Popen(argv, **kwargs)  # type: ignore[call-overload]  # noqa: S603
    return proc.pid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hebb.upgrade.helper")
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--method", required=True)
    parser.add_argument("--grace", type=float, default=30.0)
    parser.add_argument("--home", required=True)
    parser.add_argument("--port", type=int, default=8321)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    return run_upgrade(
        home_dir=Path(args.home),
        method=args.method,
        parent_pid=args.parent_pid,
        grace=args.grace,
        port=args.port,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
