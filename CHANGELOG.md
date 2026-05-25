# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **OS-managed background service is now the only supported way to run
  Hebb Mind.** `hebb service install` registers the server with launchd
  (macOS), systemd (Linux), or Task Scheduler (Windows) and starts it.
  Defaults to `--scope user` — no admin or sudo. `--scope system` is the
  opt-in elevated path. New subcommands: `hebb service {install,uninstall,
  start,stop,restart}`. Internal foreground entrypoint is the hidden
  `hebb _serve` command, invoked only by the service manager.
- **`hebb console`** — open the Web Console in your default browser with one
  command. `--print` outputs the URL only (CI / SSH friendly).
- `hebb doctor` now reports the OS service registration state alongside
  the HTTP health check.
- Community health files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue and pull
  request templates under `.github/`, `CODEOWNERS`, and a `dependabot.yml`
  config covering `pip` and `github-actions`.

### Removed

- **Breaking:** `hebb start`, `hebb stop`, `hebb restart`, the
  `--daemon` flag, and the workspace `hebb.pid` file. Use the new
  `hebb service` subcommands instead. The MCP server and Claude Code
  hooks now ask the OS service manager to start the server on demand.
- **Breaking:** CLI surface cleanup. No backwards-compatible aliases.
  - `hebb init` removed — `hebb setup` already creates the workspace on
    first run.
  - `hebb workspace` removed — use `hebb config get workspace`.
  - `hebb service status` removed — merged into top-level `hebb status`,
    which now shows OS service registration, HTTP health, and scheduler
    jobs in a single view.
  - `hebb cc <subcommand>` renamed to `hebb claude-code <subcommand>` for
    parity with `hebb codex`. Existing Claude Code installations must
    re-run `hebb claude-code install --scope user` (or `project`) so the
    settings.json hook commands point at the new name; the uninstaller
    still recognises the legacy `cc` pattern so cleanup works either way.
  - `hebb mcp` is now a group; the stdio server is started via
    `hebb mcp serve`. MCP client configs that point at the `hebb-mcp`
    console-script entry point are unaffected.
- CI: `mypy --strict` step, `actions/setup-python` pip caching, coverage
  uploaded as a workflow artifact, separate docs-build verification job that
  runs on PRs touching `repo_pages/**`, and workflow-level concurrency
  cancellation.

### Changed

- **Project renamed `hippocampus` → Hebb Mind.** The name honors Canadian
  neuropsychologist Donald O. Hebb and his learning rule — *neurons that fire
  together, wire together*. This is a **breaking change**:
  - PyPI package `afx-hippocampus` → `hebb-mind`; install with `pip install hebb-mind`.
  - CLI command `hippocampus` → `hebb`; MCP entry point `hippocampus-mcp` → `hebb-mcp`.
  - Python import `hippocampus` → `hebb`; public facade class `Hippocampus` → `HebbMind`;
    base exception `HippocampusError` → `HebbMindError`.
  - Config file `hippocampus.json` → `hebb.json`; workspace dir `~/.hippocampus/` →
    `~/.hebb/`; environment variables `HIPPOCAMPUS_*` → `HEBB_*`.
  - The MCP server registers as `hebb`.
  - "hippocampus" is retained **only** as the name of the working-memory partition
    (`mem_hippocampus`) — the inbox where new memories land before consolidation.
- `publish.yml` now runs the test matrix (lint + mypy + pytest on Python
  3.10 – 3.13) before building and uploading to PyPI, so a broken `main` can
  no longer ship a release.
- CI test matrix expanded to cover Python 3.10, 3.11, 3.12, and 3.13 to match
  the versions advertised in `pyproject.toml`.
- `CHANGELOG.md` rewritten to follow the Keep a Changelog format.

## [0.1.1] - 2026-05-12

### Added

- **CLI**: `hebb doctor`, `hebb model`, and `hebb setup`
  commands for installation health checks, embedding-model selection, and
  guided initialisation.
- **Embedding catalog**: language- and region-aware model selection so
  English, Chinese, and multilingual deployments pick sensible defaults.
- **Codex integration**: install / uninstall commands for registering
  Hebb Mind as an MCP server in Codex CLI environments.
- **Claude Code integration**: MCP service hooks for memory management,
  including ingest and consolidation triggers.
- **Conversation ingest pipeline**: `POST /api/v1/ingest/conversation`
  endpoint, transcript parsing, turn-summary extraction, conversation
  normalisation, and noise stripping.
- **Query sanitiser**: cleans up LLM-generated retrieval queries before they
  hit the vector index.
- **Workspace resolution**: configuration-driven workspace discovery so
  multiple projects can share or isolate memory state.
- **System service management**: launchd integration for auto-start on macOS
  with installation tests.
- **Daily consolidation schedule**: consolidation interval is now expressed
  as a daily wall-clock time instead of a raw interval.
- **Legal disclaimer**: bilingual `LEGAL.md` covering data usage and project
  limitations.

### Changed

- `delete_expired` now returns the IDs of removed memories and prunes the
  associated tag-graph edges.
- `stop` no longer triggers a final consolidation pass; cleanup logic is
  simpler and faster.
- Storage layer recreates the embedding table when the embedding dimension
  changes, so swapping embedding models no longer corrupts the index.
- Datetime handling switched to timezone-aware UTC throughout.
- Default Python requirement lowered to 3.10.

### Fixed

- Embedding-table dimension mismatches when switching models.
- Copy-button visibility on the documentation site.
- Various README and doc link fixes.

## [0.1.0] - 2026-04-17

Initial release.

### Added

- **Memory partitions** — five brain-inspired partitions (hippocampus,
  semantic, episodic, preference, procedural) plus user-defined partitions.
- **Memory consolidation** — LLM-powered agent that processes working memory
  into long-term partitions via Agentic RAG.
- **Dynamic forgetting** — exponential-decay TTL based on access frequency
  and importance.
- **Knowledge graph** — tag-based graph with co-occurrence edges, backed by
  NetworkX + JSON.
- **Storage backends** — SQLite + sqlite-vec (default), PostgreSQL +
  pgvector (optional).
- **REST API** — full CRUD for memories and partitions, search, graph
  queries, and admin endpoints.
- **GitHub OAuth** — optional multi-user authentication (single-user local
  mode by default).
- **CLI** — `hebb init`, `hebb start`, `hebb status`.
- **Docker** — Dockerfile and docker-compose for one-command deployment.
- **Installer** — `curl | sh` with interactive backend selection.
- **Multi-model support** — OpenAI, Anthropic, Qwen, GLM, and Kimi via
  LiteLLM.

[Unreleased]: https://github.com/afx-team/hebb-mind/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/afx-team/hebb-mind/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/afx-team/hebb-mind/releases/tag/v0.1.0
