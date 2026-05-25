"""Workspace resolution — single source of truth for all data paths.

3-tier priority:
  1. HEBB_HOME env var  → explicit override
  2. ``home`` field in hebb.json or config file parent dir
  3. ~/.hebb/           → global default (OS user directory)

Data files (hebb.db, knowledge_graph.json, models/) always live
in the workspace root. Paths are computed from home_dir, not configurable
separately.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def get_default_home() -> Path:
    """Return OS-appropriate default home directory: ``~/.hebb/``."""
    return Path.home() / ".hebb"


def resolve_workspace(config_path: Path | None = None) -> Path:
    """Resolve the workspace root directory.

    Priority:
        1. ``HEBB_HOME`` environment variable (absolute path)
        2. ``home`` field in hebb.json (if set)
        3. Parent directory of *config_path* (or found ``hebb.json``)
        4. ``~/.hebb/`` (auto-created if missing)

    Returns:
        Absolute ``Path`` to the workspace root. The directory is guaranteed
        to exist on return.
    """
    # 1. Explicit env var override
    env_home = os.environ.get("HEBB_HOME")
    if env_home:
        home = Path(env_home).resolve()
        home.mkdir(parents=True, exist_ok=True)
        return home

    # 2-3. Find config file
    if config_path is None:
        from hebb.config.loader import find_config_file

        config_path = find_config_file()

    if config_path is not None and config_path.is_file():
        # 2. Check for "home" field in config
        try:
            raw = json.loads(config_path.read_text())
            home_value = raw.get("home")
            if home_value:
                home = Path(home_value)
                if not home.is_absolute():
                    home = config_path.parent / home
                home = home.resolve()
                home.mkdir(parents=True, exist_ok=True)
                return home
        except (json.JSONDecodeError, OSError):
            pass
        # 3. Config file's parent dir is the workspace
        return config_path.parent.resolve()

    # 4. Global default
    home = get_default_home()
    home.mkdir(parents=True, exist_ok=True)
    return home
