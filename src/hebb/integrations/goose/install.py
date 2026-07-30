"""Install Hebb Mind MCP into Goose config.yaml."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import click

from hebb.utils.cli_paths import hebb_mcp_command, shell_quote

EXTENSION_NAME = "hebb"


def config_path() -> Path:
    """Resolve the Goose configuration file path."""
    return Path.home() / ".config" / "goose" / "config.yaml"


def _build_yaml_block(mcp_argv: list[str]) -> str:
    """Build the Goose YAML extension entry for Hebb.

    Goose stores MCP servers under ``extensions`` with ``type: stdio``.
    The command goes in ``cmd``, arguments in ``args``.
    """
    cmd = mcp_argv[0]
    args = mcp_argv[1:]
    if args:
        args_block = "    args:\n" + "\n".join(f"      - {a}" for a in args) + "\n"
    else:
        args_block = "    args: []\n"
    return (
        f"  {EXTENSION_NAME}:\n"
        f"    type: stdio\n"
        f"    name: {EXTENSION_NAME}\n"
        f"    enabled: true\n"
        f"    cmd: {cmd}\n"
        f"{args_block}"
        f"    envs: {{}}\n"
        f"    timeout: 300\n"
    )


def _remove_hebb_block(text: str) -> str:
    """Remove the Hebb extension block from Goose YAML.

    Args:
        text: Existing config.yaml content.

    Returns:
        YAML content without the Hebb extension entry.
    """
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.rstrip()
        # Detect start of hebb block: "  hebb:" at extension indent level
        if stripped == f"  {EXTENSION_NAME}:":
            skipping = True
            continue
        if skipping:
            # Hebb block lines are indented with 4+ spaces (nested under hebb:)
            # or blank. Stop skipping when we hit a line with <= 2 spaces indent
            # (sibling extension or top-level key).
            if line.strip() and not line.startswith("    "):
                skipping = False
                output.append(line)
            # else: still in hebb block, skip
        else:
            output.append(line)
    return "".join(output)


def atomic_write(path: Path, content: str) -> None:
    """Atomically replace a UTF-8 text file, creating its parent dir."""
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


def handle() -> None:
    """Install Hebb Mind MCP into Goose.

    Raises:
        click.ClickException: If the config file has an unsupported inline
            ``extensions:`` key (e.g. ``extensions: {}``) that cannot be
            safely extended.
    """
    mcp_argv = hebb_mcp_command()
    path = config_path()

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = _remove_hebb_block(existing)

    block = _build_yaml_block(mcp_argv)

    # Match only a root-level (unindented) block-style "extensions:" header.
    # An indented "extensions:" (nested under another key) or an inline form
    # like "extensions: {}" should not trigger insertion.
    has_extensions_block = any(line.rstrip("\r\n") == "extensions:" for line in cleaned.splitlines())
    has_extensions_inline = any(
        line.lstrip().startswith("extensions:") and line.rstrip("\r\n") != "extensions:"
        for line in cleaned.splitlines()
    )

    if has_extensions_inline and not has_extensions_block:
        raise click.ClickException(
            f"Goose config has an inline 'extensions:' key that cannot be safely "
            f"extended. Please convert it to block style (a line with just "
            f"'extensions:') in {path}."
        )

    if not has_extensions_block:
        if cleaned and not cleaned.endswith("\n"):
            cleaned += "\n"
        cleaned += "extensions:\n" + block
    else:
        # Insert hebb block right after the root-level "extensions:" line
        lines = cleaned.splitlines(keepends=True)
        output: list[str] = []
        inserted = False
        for line in lines:
            output.append(line)
            if not inserted and line.rstrip("\r\n") == "extensions:":
                output.append(block)
                inserted = True
        if not inserted:
            # Fallback: should not happen given has_extensions_block check
            if cleaned and not cleaned.endswith("\n"):
                cleaned += "\n"
            cleaned += "extensions:\n" + block
        else:
            cleaned = "".join(output)

    atomic_write(path, cleaned)

    click.secho("Installed Hebb Mind for Goose.", fg="green")
    click.echo(f"  Config: {path}")
    click.echo(f"  Server command: {shell_quote(mcp_argv)}")
    click.echo("Verify with: goose info -v")
    click.echo("Start a new Goose session to activate the integration.")
