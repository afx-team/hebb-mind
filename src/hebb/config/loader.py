"""Config loading: hebb.json is the single source of truth.

All configuration values live in hebb.json. Use ``hebb config set <key>
<value>`` to modify config from the CLI.

Environment variable overrides
------------------------------
Two env vars do override hebb.json, in this precedence (env wins over file):

  * ``HEBB_HOME`` — overrides the workspace root that resolves ``home_dir``
    and therefore ``db_path`` / ``kg_path`` (see :mod:`hebb.config.workspace`).
    Highest priority; independent of any ``home`` field in hebb.json.
  * ``HEBB_AUTO_UPGRADE`` — ``auto`` / ``notify`` / ``off`` overrides
    ``auto_upgrade_mode`` for fleet/CI control.

Data file paths (db_path, kg_path) are computed from the workspace root
and are not stored in the config file.
"""

from __future__ import annotations

import json
import os
import tempfile
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

    Env var overrides (top priority, override hebb.json):
        - ``HEBB_AUTO_UPGRADE`` — ``auto`` / ``notify`` / ``off`` for fleet/CI control
    """
    values: dict[str, Any] = {}

    path = config_path or find_config_file()
    if path and path.exists():
        with open(path) as f:
            raw = json.load(f)
        for k, v in raw.items():
            if k in Settings.model_fields:
                values[k] = v

    env_mode = os.environ.get("HEBB_AUTO_UPGRADE")
    if env_mode in ("auto", "notify", "off"):
        values["auto_upgrade_mode"] = env_mode

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


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write *data* as JSON to *path* atomically.

    Writes to a temp file in the same directory (so ``os.replace`` is a same-
    filesystem atomic rename) and fsyncs before the rename, so a crash mid-write
    can never leave a truncated hebb.json.

    Args:
        path: Destination config file.
        data: JSON-serializable mapping to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class _ConfigLock:
    """Cross-process advisory lock guarding hebb.json read-modify-write.

    Uses ``fcntl.flock`` on POSIX so concurrent CLI ``config set`` and server
    ``PUT /config`` writers serialize instead of clobbering each other or
    leaving a half-written file. A no-op on platforms without ``fcntl``
    (Windows), where the atomic ``os.replace`` still prevents truncation.
    """

    def __init__(self, path: Path) -> None:
        self._lock_path = path.with_name(f".{path.name}.lock")
        self._fd: int | None = None

    def __enter__(self) -> _ConfigLock:
        try:
            import fcntl
        except ImportError:
            return self
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fd is None:
            return
        try:
            import fcntl

            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except ImportError:
            pass
        finally:
            os.close(self._fd)
            self._fd = None


def update_config_field(key: str, value: str, config_path: Path | None = None) -> tuple[Path, Any]:
    """Update a single field in hebb.json atomically.

    Handles type coercion: bool, int, float, None, or str. The read-modify-write
    runs under a cross-process file lock and the result is written via a temp
    file + ``os.replace`` so concurrent CLI/server writers can neither clobber
    each other nor leave a truncated config behind.

    Args:
        key: A valid ``Settings`` field name.
        value: The raw string value (coerced to the field's type).
        config_path: Explicit hebb.json path, or ``None`` to auto-discover.

    Returns:
        ``(path, coerced_value)`` — the config file path and the value after
        Pydantic validation, so callers can apply the same value to a live
        Settings instance without re-loading the file.

    Raises:
        FileNotFoundError: If the config file does not exist.
        KeyError: If *key* is not a known ``Settings`` field.
    """
    path = config_path or find_config_file() or Path("hebb.json")
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    if key not in Settings.model_fields:
        raise KeyError(f"Unknown config key: {key!r}")

    # Coerce value based on the field's type annotation
    field_info = Settings.model_fields[key]
    annotation = field_info.annotation
    coerced = _coerce_value(value, annotation)

    with _ConfigLock(path):
        with open(path) as f:
            data = json.load(f)

        data[key] = coerced
        settings = Settings(**{k: v for k, v in data.items() if k in Settings.model_fields})
        validated = getattr(settings, key)
        data[key] = validated

        _atomic_write_json(path, data)
    return path, validated


def update_forgetting_overrides(
    overrides: dict[str, dict[str, Any]], config_path: Path | None = None
) -> tuple[Path, dict[str, Any]]:
    """Atomically replace the ``forgetting_overrides`` map in hebb.json.

    This is the structured-config counterpart to :func:`update_config_field`
    (which only handles scalar key/value edits): the forgetting overrides are a
    nested ``{partition_id: {half_life_days, k_importance, k_access, threshold, enabled}}`` map, so the
    whole map is written under the same cross-process lock and atomic temp-file +
    ``os.replace`` as the scalar writer. The map is validated through ``Settings``
    before being persisted, so a malformed override is rejected rather than saved.

    Args:
        overrides: The complete desired overrides map (partition id -> override
            fields). Pass an empty dict to clear all overrides.
        config_path: Explicit hebb.json path, or ``None`` to auto-discover.

    Returns:
        ``(path, validated_overrides)`` — the config file path and the map after
        Pydantic validation, so callers can sync a live Settings instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    path = config_path or find_config_file() or Path("hebb.json")
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with _ConfigLock(path):
        with open(path) as f:
            data = json.load(f)

        data["forgetting_overrides"] = overrides
        # Validate the whole map through Settings (rejects malformed overrides)
        # and write back the normalized form.
        settings = Settings(**{k: v for k, v in data.items() if k in Settings.model_fields})
        validated = settings.model_dump()["forgetting_overrides"]
        data["forgetting_overrides"] = validated

        _atomic_write_json(path, data)
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
