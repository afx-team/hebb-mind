"""Distribution-surface audit tests (Lane A-distribution) -- the command-drift guard.

Guards against the command-drift class of defects where a shipped surface --
the Claude Code plugin manifest, the Codex hooks manifest, the Docker image, or
any user-facing doc (the two READMEs, the VitePress site under ``repo_pages/``,
the runnable ``examples/``) -- references a ``hebb`` command that does not exist
in the registered Click command tree. A typo, a renamed subcommand, or two
install paths drifting apart silently breaks every install or misleads every
reader, so these tests resolve each shipped command string back to a real Click
command.

This is the CI guard recommended by audit finding C0-2
(``reports/audit/core-system-audit-2026-06-07.md``) and roadmap item S1
(``reports/design/capability-gap-roadmap-2026-06-11.md``). It is exactly the
class of regression that once shipped ``hebb cc write`` (wrong group name *and*
a nonexistent ``write`` subcommand) and ``hebb start`` (nonexistent) to users.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import click

from hebb.cli.main import main

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
CODEX_HOOKS_JSON = REPO_ROOT / ".codex" / "hooks.json"
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"

# A registered Click command/group name (lowercase, may contain ``-``/``_``;
# the hidden ``_serve`` entrypoint starts with ``_``). Anything that does not
# match -- an option (``--scope``), a synopsis placeholder (``[--scope]``,
# ``<provider>/<model>``, ``MODEL_ID``), or a positional argument -- marks the
# end of the resolvable command path.
_COMMAND_TOKEN = re.compile(r"^[a-z_][a-z0-9_-]*$")

# Commands intentionally documented before they exist (roadmap items). Each
# entry is verified to be genuinely unregistered by
# ``test_known_unimplemented_commands_are_still_unregistered`` -- so the moment
# such a command ships, that test fails until the entry is removed and the
# drift guard starts covering it for real. You cannot leave a stale exception.
#   - "export": repo_pages/faq.md -- "A first-class `hebb export` command is on
#     the roadmap" (mirrored in repo_pages/zh/faq.md).
KNOWN_UNIMPLEMENTED_COMMANDS: frozenset[str] = frozenset({"export"})


def _resolve_command(tokens: list[str]) -> bool:
    """Resolve a token path (e.g. ``["claude-code", "recall"]``) to a command.

    Walks the Click group tree token by token. Resolution stops -- successfully
    -- as soon as a leaf (non-group) command is reached or a non-command token
    appears (an option like ``--scope``, or a synopsis placeholder/argument like
    ``[--scope]`` / ``<provider>/<model>`` / ``MODEL_ID``), since everything
    after that is arguments rather than sub-command names. Resolution fails only
    when a concrete sub-command token does not exist under its group -- the
    drift this guard exists to catch.

    Args:
        tokens: The command path with the leading ``hebb`` executable removed.

    Returns:
        True if every concrete sub-command token resolves to a registered Click
        command; False on the first sub-command token that does not.
    """
    cmd: click.Command = main
    ctx = click.Context(main)
    for token in tokens:
        if not isinstance(cmd, click.Group):
            return True  # leaf reached; remaining tokens are arguments
        if not _COMMAND_TOKEN.match(token):
            return True  # option / placeholder / argument -- path ends here
        sub = cmd.get_command(ctx, token)
        if sub is None:
            return False
        cmd = sub
    return True


def _extract_hook_commands(manifest: Path) -> list[str]:
    """Collect every ``command`` string from a hook manifest's hook entries.

    Args:
        manifest: Path to a JSON file with a ``hooks`` section.

    Returns:
        The list of command strings found under every hook entry.
    """
    data = json.loads(manifest.read_text())
    commands: list[str] = []
    for event_groups in data["hooks"].values():
        for group in event_groups:
            for hook in group["hooks"]:
                if hook.get("type") == "command":
                    commands.append(hook["command"])
    return commands


def _hebb_invocations(command: str) -> list[list[str]]:
    """Return the ``hebb`` sub-command token paths embedded in a shell command.

    Args:
        command: A shell command string that may contain one or more ``hebb``
            invocations (e.g. a Dockerfile ``CMD`` chain).

    Returns:
        A list of token paths (each with the leading ``hebb`` stripped), one per
        ``hebb`` invocation found.
    """
    invocations: list[list[str]] = []
    for match in re.finditer(r"\bhebb\b([^;&|]*)", command):
        tail = match.group(1).strip()
        if not tail:
            invocations.append([])
            continue
        tokens: list[str] = []
        for tok in tail.split():
            if tok.startswith("-"):
                break  # first option ends the sub-command path
            tokens.append(tok)
        invocations.append(tokens)
    return invocations


def test_plugin_hook_commands_resolve() -> None:
    """Every command in the Claude Code plugin manifest is a real CLI command."""
    commands = _extract_hook_commands(PLUGIN_JSON)
    assert commands, "plugin.json declared no hook commands"
    for command in commands:
        tokens = command.split()
        assert tokens[0] == "hebb", f"unexpected executable: {command!r}"
        assert _resolve_command(tokens[1:]), f"unresolved command: {command!r}"


def test_codex_hook_commands_resolve() -> None:
    """Every command in the Codex hooks manifest is a real CLI command."""
    commands = _extract_hook_commands(CODEX_HOOKS_JSON)
    assert commands, "hooks.json declared no hook commands"
    for command in commands:
        tokens = command.split()
        assert tokens[0] == "hebb", f"unexpected executable: {command!r}"
        assert _resolve_command(tokens[1:]), f"unresolved command: {command!r}"


def test_dockerfile_cmd_references_real_serve_command() -> None:
    """The Dockerfile CMD chain only invokes registered ``hebb`` commands."""
    text = DOCKERFILE.read_text()
    cmd_line = next(
        (line for line in text.splitlines() if line.lstrip().startswith("CMD")),
        None,
    )
    assert cmd_line is not None, "no CMD line found in Dockerfile"
    # The serve entrypoint is what actually starts the server.
    assert "hebb _serve" in cmd_line
    assert "hebb start" not in cmd_line, "nonexistent 'hebb start' still present"
    for tokens in _hebb_invocations(cmd_line):
        if not tokens:
            continue
        assert _resolve_command(tokens), f"unresolved CMD command: {tokens}"


# --------------------------------------------------------------------------- #
# Doc surface: README, the VitePress site, and the runnable examples.          #
# --------------------------------------------------------------------------- #

# Tracked doc roots scanned for ``hebb`` command strings. ``git ls-files`` scopes
# this to *shipped* (committed) files, which auto-excludes gitignored vendored
# trees (e.g. ``repo_pages/node_modules``) and the VitePress build/cache output.
_DOC_ROOTS = ("README.md", "README_ZH.md", "repo_pages", "examples")

# A fenced code block: ``` or ~~~ (>=3), an info string, body, matching close.
_FENCE = re.compile(
    r"^[ \t]*(`{3,}|~{3,})[^\n]*\n(.*?)^[ \t]*\1[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
# An inline code span: `like this`.
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# Shell separators that split one snippet into independent commands.
_SHELL_SEPARATORS = re.compile(r"&&|\|\||[;|\n]")
# A leading shell prompt (``$ `` / ``> ``) shown in console transcripts.
_SHELL_PROMPT = re.compile(r"^\s*[$>]\s+")


def _doc_files() -> list[Path]:
    """Every tracked doc file that may contain a ``hebb`` command string.

    Returns:
        Markdown files anywhere under the doc roots plus ``.py`` example files,
        excluding the VitePress ``.vitepress/`` build/cache/theme directory.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *_DOC_ROOTS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    files: list[Path] = []
    for rel in result.stdout.split("\0"):
        if not rel:
            continue
        path = REPO_ROOT / rel
        if ".vitepress" in path.parts:
            continue  # build output / cache / theme, not authored docs
        if path.suffix == ".md" or (path.suffix == ".py" and "examples" in path.parts):
            files.append(path)
    return files


def _command_paths(snippet: str) -> list[list[str]]:
    """Extract ``hebb`` sub-command token paths from one code snippet.

    Splits a fenced-block body or inline code span on shell separators
    (``;`` ``&&`` ``||`` ``|`` newline), strips any shell prompt, and keeps only
    segments whose first bare word is ``hebb``. This drops ``from hebb import
    ...`` (first word ``from``), prose, and piped non-hebb commands
    (``hebb config list | grep llm`` keeps only the ``hebb`` half).

    Args:
        snippet: Raw text of a fenced code block body or an inline code span.

    Returns:
        One token path per ``hebb`` invocation, each with ``hebb`` stripped.
    """
    paths: list[list[str]] = []
    for raw in _SHELL_SEPARATORS.split(snippet):
        segment = _SHELL_PROMPT.sub("", raw.strip())
        words = segment.split()
        if words and words[0] == "hebb":
            paths.append(words[1:])
    return paths


def _doc_command_paths(path: Path) -> list[list[str]]:
    """Collect every ``hebb`` command token path documented in one file.

    Markdown files are scanned in both fenced code blocks and inline code spans.
    ``.py`` example files are scanned only for inline code spans (backtick-quoted
    commands inside strings/docstrings), so the ``from hebb import ...`` package
    import is never mistaken for a CLI invocation.

    Args:
        path: The doc file to scan.

    Returns:
        Token paths (``hebb`` stripped), one per documented invocation.
    """
    text = path.read_text(encoding="utf-8")
    paths: list[list[str]] = []
    if path.suffix == ".md":

        def _drain_fence(match: re.Match[str]) -> str:
            paths.extend(_command_paths(match.group(2)))
            return "\n"  # remove the fence so its body isn't re-scanned inline

        text = _FENCE.sub(_drain_fence, text)
    for match in _INLINE_CODE.finditer(text):
        paths.extend(_command_paths(match.group(1)))
    return paths


def test_doc_command_strings_resolve() -> None:
    """Every ``hebb`` command in shipped docs resolves to a real CLI command."""
    total = 0
    failures: list[str] = []
    for path in _doc_files():
        rel = path.relative_to(REPO_ROOT)
        for tokens in _doc_command_paths(path):
            total += 1
            if tokens and tokens[0] in KNOWN_UNIMPLEMENTED_COMMANDS:
                continue
            if not _resolve_command(tokens):
                failures.append(f"  {rel}: hebb {' '.join(tokens)}")
    # Guard against a silently broken extractor that finds nothing and passes
    # vacuously; the doc set realistically holds hundreds of invocations.
    assert total > 50, f"extractor found only {total} hebb commands -- likely broken"
    assert not failures, (
        "Documented `hebb` commands that do not resolve to a registered Click "
        "command. Fix the doc, rename the command, or -- for an intentional "
        "roadmap command -- add it to KNOWN_UNIMPLEMENTED_COMMANDS:\n" + "\n".join(sorted(set(failures)))
    )


def test_known_unimplemented_commands_are_still_unregistered() -> None:
    """Roadmap-only commands must stay unregistered; once shipped, drop them.

    Keeps ``KNOWN_UNIMPLEMENTED_COMMANDS`` from rotting into a silent allowlist:
    implementing ``hebb export`` makes this fail until its entry is removed, at
    which point ``test_doc_command_strings_resolve`` covers it for real.
    """
    for name in sorted(KNOWN_UNIMPLEMENTED_COMMANDS):
        assert not _resolve_command([name]), (
            f"'hebb {name}' now resolves to a registered command -- remove it "
            "from KNOWN_UNIMPLEMENTED_COMMANDS so the drift guard covers it"
        )
