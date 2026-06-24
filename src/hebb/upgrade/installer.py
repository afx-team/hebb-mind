"""Install-method detection + upgrade command construction.

Determines *how* the running ``hebb-mind`` was installed — editable / pipx /
uv-tool / pip — so the upgrade helper runs the matching upgrade command, and
refuses the cases we must never auto-upgrade: editable dev checkouts and
system-managed interpreters. See ``reports/design/auto-upgrade.md``.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from importlib.metadata import Distribution
from pathlib import Path
from typing import Literal

import hebb

PACKAGE_NAME = "hebb-mind"

Method = Literal["editable", "pipx", "uv-tool", "pip", "system", "unknown"]

# Methods we refuse to auto-upgrade — the user must act manually. The reason is
# a stable machine string; the console maps ``method`` to a localized message
# and only falls back to this text.
_REFUSED_METHODS: dict[Method, str] = {
    "editable": "editable/development install — upgrade with git pull",
    "system": "system-managed Python — upgrade via your OS package manager",
    "unknown": "could not determine how hebb-mind was installed",
}


@dataclass(frozen=True)
class UpgradeCommand:
    """A resolved upgrade plan for the detected install method.

    Attributes:
        method: The detected install method.
        argv: The command to run, or ``[]`` when not auto-upgradable.
        env: Extra environment variables to overlay on the helper's env.
        cwd: Working directory for the upgrade command.
        auto_upgradable: ``False`` for editable / system / unknown installs.
        refusal_reason: Human-readable reason when ``auto_upgradable`` is False.
    """

    method: Method
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    cwd: Path = field(default_factory=Path.home)
    auto_upgradable: bool = True
    refusal_reason: str | None = None


def _is_editable_install() -> bool:
    """Return True when ``hebb-mind`` is installed editable / from a dev tree.

    Authoritative signal is PEP 610 ``direct_url.json`` (written with the
    ``editable`` flag by ``pip install -e``); the git-tree heuristic is a
    fallback for environments that lack that metadata.
    """
    try:
        dist = Distribution.from_name(PACKAGE_NAME)
        raw = dist.read_text("direct_url.json")
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("dir_info", {}).get("editable") is True:
                return True
    except Exception:
        pass
    try:
        pkg_dir = Path(hebb.__file__).resolve().parent  # .../src/hebb
        for parent in pkg_dir.parents:
            pp = parent / "pyproject.toml"
            if not pp.is_file():
                continue
            # Only a *hebb-mind* source tree counts — a user venv nested inside
            # an unrelated project (its own pyproject.toml above site-packages)
            # must NOT be misread as editable. Matching the package name avoids
            # both that false-positive and the ``.git``-deleted false-negative.
            try:
                text = pp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if 'name = "hebb-mind"' in text or "name = 'hebb-mind'" in text:
                return True
    except Exception:
        pass
    return False


def _classify_executable() -> Method:
    """Classify the running interpreter as ``pipx`` / ``uv-tool`` / ``pip``.

    Prefers tool marker files in the venv root (``pipx_metadata.json`` /
    ``uv-receipt.toml``) so a custom ``PIPX_HOME`` / ``UV_TOOL_DIR`` without the
    tool name in its path is still classified correctly; falls back to the
    conventional path layout.
    """
    venv_root = Path(sys.prefix)
    if (venv_root / "pipx_metadata.json").is_file():
        return "pipx"
    if (venv_root / "uv-receipt.toml").is_file():
        return "uv-tool"
    norm = str(Path(sys.executable).resolve()).replace("\\", "/").lower()
    if "pipx/venvs/hebb-mind" in norm:
        return "pipx"
    if "uv/tools/hebb-mind" in norm:
        return "uv-tool"
    return "pip"


def _is_system_python() -> bool:
    """Return True for a system-managed interpreter we must not pip-upgrade.

    A virtualenv (``sys.prefix != sys.base_prefix`` — covers venv / pipx /
    uv-tool) is always user-writable and upgradable. Only a non-venv
    interpreter rooted in a system location is refused. The comparison is
    normalized (forward slashes, lowercase) so a Windows path like
    ``C:\\PROGRAM FILES`` is still recognized.
    """
    if sys.prefix != sys.base_prefix:
        return False
    prefix = str(Path(sys.prefix).resolve()).replace("\\", "/").lower()
    system_roots = (
        "/usr",
        "/library/frameworks",
        "/system",
        "c:/program files",  # also matches "c:/program files (x86)"
        "c:/programdata",
        "c:/windows",
    )
    return any(prefix.startswith(root) for root in system_roots)


def detect_method() -> Method:
    """Detect how the running ``hebb-mind`` was installed.

    Returns:
        One of ``editable`` / ``pipx`` / ``uv-tool`` / ``pip`` / ``system``.
        The first three (and a non-system ``pip``) are auto-upgradable;
        ``editable`` and ``system`` are refused.
    """
    if _is_editable_install():
        return "editable"
    method = _classify_executable()
    if method in ("pipx", "uv-tool"):
        return method
    if _is_system_python():
        return "system"
    return "pip"


def build_command(method: Method | None = None) -> UpgradeCommand:
    """Build the upgrade command for ``method`` (auto-detected when ``None``).

    Args:
        method: Install method to build for; auto-detected when omitted.

    Returns:
        An :class:`UpgradeCommand`. Refused methods (editable / system /
        unknown) carry ``auto_upgradable=False`` and ``argv == []``.
    """
    if method is None:
        method = detect_method()

    if method in _REFUSED_METHODS:
        return UpgradeCommand(
            method=method,
            argv=[],
            auto_upgradable=False,
            refusal_reason=_REFUSED_METHODS[method],
        )

    env: dict[str, str] = {}
    index_url = os.environ.get("HEBB_PYPI_INDEX_URL")

    if method == "pipx":
        pipx = shutil.which("pipx")
        if pipx:
            argv = [pipx, "upgrade", PACKAGE_NAME]
        else:
            # pipx venvs ship pip, so when pipx isn't on PATH we can still
            # upgrade in place via the venv interpreter (sys.executable).
            argv = [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME]
        if index_url:
            env["PIP_INDEX_URL"] = index_url
    elif method == "uv-tool":
        uv = shutil.which("uv")
        if not uv:
            # uv tool venvs have no pip to fall back on — refuse with a clear
            # action instead of failing later with a cryptic "uv: not found".
            return UpgradeCommand(
                method=method,
                argv=[],
                auto_upgradable=False,
                refusal_reason="uv not found on PATH — run 'uv tool upgrade hebb-mind' manually",
            )
        argv = [uv, "tool", "upgrade", PACKAGE_NAME]
        if index_url:
            env["UV_INDEX_URL"] = index_url
    else:  # pip
        argv = [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME]
        if index_url:
            env["PIP_INDEX_URL"] = index_url

    return UpgradeCommand(method=method, argv=argv, env=env, auto_upgradable=True)
