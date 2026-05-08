"""Config loading: hippocampus.json is the single source of truth.

All configuration lives in hippocampus.json. No environment variable overrides.
Use `hippocampus config set <key> <value>` to modify config from the CLI.

Data file paths (db_path, kg_path) are computed from the workspace root
and are not stored in the config file.
"""

from __future__ import annotations

import json
from pathlib import Path

from hippocampus.config.settings import Settings
from hippocampus.config.workspace import resolve_workspace


def find_config_file(start_dir: Path | None = None) -> Path | None:
    """Walk up from start_dir looking for hippocampus.json."""
    d = start_dir or Path.cwd()
    for parent in [d, *d.parents]:
        candidate = parent / "hippocampus.json"
        if candidate.is_file():
            return candidate
    return None


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from hippocampus.json + code defaults.

    Resolves the workspace root and sets ``settings.home_dir`` so that
    ``settings.db_path`` and ``settings.kg_path`` return absolute paths.
    """
    values: dict = {}

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
    """Write current settings back to hippocampus.json."""
    path = config_path or find_config_file() or Path("hippocampus.json")
    data = settings.model_dump()
    # Exclude computed fields and None values
    clean = {k: v for k, v in data.items() if v is not None and k not in ("home_dir",)}
    with open(path, "w") as f:
        json.dump(clean, f, indent=2)
        f.write("\n")
    return path


def create_default_config(target: Path) -> None:
    """Write hippocampus.json with all defaults."""
    defaults = Settings()
    data = defaults.model_dump()
    # Exclude computed fields
    clean = {k: v for k, v in data.items() if k not in ("home_dir",)}
    with open(target, "w") as f:
        json.dump(clean, f, indent=2)
        f.write("\n")


def update_config_field(key: str, value: str, config_path: Path | None = None) -> Path:
    """Update a single field in hippocampus.json.

    Handles type coercion: bool, int, float, None, or str.
    """
    path = config_path or find_config_file() or Path("hippocampus.json")
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

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return path


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
