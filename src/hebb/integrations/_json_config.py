"""Shared helpers for JSON-based MCP client installers.

Most MCP clients (Gemini CLI, Cline, Cursor, LM Studio, …) store their
server configuration in a JSON file with a ``mcpServers`` top-level key.
This module factors out the common read / upsert / remove logic so each
client installer only needs to supply the config *path* and the *key name*
(which is almost always ``"mcpServers"``).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import click


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON config file, returning ``{}`` if it does not exist.

    Args:
        path: Configuration file path.

    Returns:
        Parsed JSON object (top-level dict).

    Raises:
        click.ClickException: If the file exists but cannot be parsed.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise click.ClickException(f"{path} must contain a JSON object at the top level")
    return data


def atomic_write(path: Path, content: str) -> None:
    """Atomically replace a UTF-8 text file, creating its parent dir.

    Args:
        path: Destination file.
        content: Complete replacement content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def upsert_server(
    path: Path,
    key: str,
    server_name: str,
    entry: dict[str, Any],
) -> bool:
    """Insert or replace an MCP server entry in a JSON config file.

    Args:
        path: Configuration file path.
        key: Top-level key holding the servers mapping (e.g. ``"mcpServers"``).
        server_name: Name of the server entry to upsert.
        entry: Server configuration dict (``command``, ``args``, ``env`` …).

    Returns:
        ``True`` if the file was written, ``False`` if it was already correct.
    """
    data = load_json(path)
    servers = data.get(key)
    if not isinstance(servers, dict):
        servers = {}
        data[key] = servers
    if servers.get(server_name) == entry:
        return False
    servers[server_name] = entry
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return True


def remove_server(
    path: Path,
    key: str,
    server_name: str,
) -> bool:
    """Remove an MCP server entry from a JSON config file.

    Args:
        path: Configuration file path.
        key: Top-level key holding the servers mapping.
        server_name: Name of the server entry to remove.

    Returns:
        ``True`` if the file was changed, ``False`` if the entry was absent.
    """
    data = load_json(path)
    servers = data.get(key)
    if not isinstance(servers, dict) or server_name not in servers:
        return False
    del servers[server_name]
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return True
