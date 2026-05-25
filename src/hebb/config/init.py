"""Workspace initialization — bootstrap a Hebb Mind workspace on disk.

Pure library functions used by `hebb setup` and tests. No Click dependency.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from hebb.config.loader import create_default_config, load_settings
from hebb.config.settings import Settings
from hebb.config.workspace import get_default_home
from hebb.storage.factory import create_stores


@dataclass(frozen=True)
class InitResult:
    """Result of workspace initialization."""

    settings_path: Path
    settings: Settings


def default_init_target() -> Path:
    """Return the default initialization target directory.

    Returns:
        ``HEBB_HOME`` when set, otherwise ``~/.hebb``.
    """
    env_home = os.environ.get("HEBB_HOME")
    if env_home:
        return Path(env_home).resolve()
    return get_default_home()


def initialize_workspace(target_dir: str | Path | None = None, force: bool = False) -> InitResult:
    """Initialize a Hebb Mind workspace.

    Args:
        target_dir: Directory to initialize. Defaults to ``HEBB_HOME`` or ``~/.hebb``.
        force: Whether to overwrite config and reset SQLite storage.

    Returns:
        Initialized settings path and loaded settings.
    """
    target = Path(target_dir).resolve() if target_dir else default_init_target()
    target.mkdir(parents=True, exist_ok=True)

    config_path = target / "hebb.json"

    if not config_path.exists() or force:
        create_default_config(config_path)

    settings = load_settings(config_path)

    if force and settings.storage_type == "sqlite":
        db_path = Path(settings.db_path)
        for suffix in ("", "-wal", "-shm"):
            p = db_path.parent / (db_path.name + suffix)
            if p.exists():
                p.unlink()

    async def _init_storage() -> None:
        ctx = await create_stores(settings)
        await ctx.partition_store.ensure_defaults()
        await ctx.close()

    asyncio.run(_init_storage())

    kg_path = Path(settings.kg_path)
    if force or not kg_path.exists():
        kg_path.parent.mkdir(parents=True, exist_ok=True)
        kg_path.write_text(json.dumps({"nodes": [], "edges": [], "version": 1}, indent=2))

    return InitResult(settings_path=config_path, settings=settings)
