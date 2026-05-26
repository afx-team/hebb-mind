"""Config loading: hebb.json is the single source of truth.

All configuration lives in hebb.json. No environment variable overrides.
Use `hebb config set <key> <value>` to modify config from the CLI.

Data file paths (db_path, kg_path) are computed from the workspace root
and are not stored in the config file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hebb.config.settings import Settings
from hebb.config.workspace import resolve_workspace


def find_config_file(start_dir: Path | None = None) -> Path | None:
    """Find the active hebb.json.

    Search order:
        1. Current directory and parents.
        2. HEBB_HOME/hebb.json.
        3. ~/.hebb/hebb.json.
    """
    d = start_dir or Path.cwd()
    for parent in [d, *d.parents]:
        candidate = parent / "hebb.json"
        if candidate.is_file():
            return candidate

    env_home = os.environ.get("HEBB_HOME")
    if env_home:
        candidate = Path(env_home).expanduser() / "hebb.json"
        if candidate.is_file():
            return candidate
        return None

    candidate = Path.home() / ".hebb" / "hebb.json"
    if candidate.is_file():
        return candidate
    return None


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from hebb.json + code defaults.

    Resolves the workspace root and sets ``settings.home_dir`` so that
    ``settings.db_path`` and ``settings.kg_path`` return absolute paths.
    """
    values: dict[str, Any] = {}

    path = config_path or find_config_file()
    if path and path.exists():
        with open(path) as f:
            raw = json.load(f)
        for k, v in raw.items():
            if k in Settings.model_fields:
                values[k] = v

    settings = Settings(**values)

    # Resolve workspace and set home_dir
    workspace = resolve_workspace(config_path=path)
    settings.home_dir = workspace

    return settings


def save_settings(settings: Settings, config_path: Path | None = None) -> Path:
    """Write current settings back to hebb.json."""
    path = config_path or find_config_file() or Path("hebb.json")
    data = settings.model_dump()
    # Exclude computed fields and None values
    clean = {k: v for k, v in data.items() if v is not None and k not in ("home_dir",)}
    with open(path, "w") as f:
        json.dump(clean, f, indent=2)
        f.write("\n")
    return path


def create_default_config(target: Path) -> None:
    """Write hebb.json with all defaults."""
    defaults = Settings()
    data = defaults.model_dump()
    # Exclude computed fields
    clean = {k: v for k, v in data.items() if k not in ("home_dir",)}
    with open(target, "w") as f:
        json.dump(clean, f, indent=2)
        f.write("\n")


def update_config_field(key: str, value: str, config_path: Path | None = None) -> tuple[Path, Any]:
    """Update a single field in hebb.json.

    Handles type coercion: bool, int, float, None, or str.

    Returns:
        ``(path, coerced_value)`` — the config file path and the value after
        Pydantic validation, so callers can apply the same value to a live
        Settings instance without re-loading the file.
    """
    path = config_path or find_config_file() or Path("hebb.json")
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        data = json.load(f)

    if key not in Settings.model_fields:
        raise KeyError(f"Unknown config key: {key!r}")

    # Coerce value based on the field's type annotation
    field_info = Settings.model_fields[key]
    annotation = field_info.annotation

    coerced = _coerce_value(value, annotation)
    data[key] = coerced
    settings = Settings(**{k: v for k, v in data.items() if k in Settings.model_fields})
    validated = getattr(settings, key)
    data[key] = validated

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return path, validated


def _coerce_value(value: str, annotation: type | None) -> str | int | float | bool | None:
    """Coerce a string value to the appropriate Python type."""
    if value.lower() == "null" or value.lower() == "none":
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    # Try int, then float, then keep as string
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
