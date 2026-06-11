---
description: "Install hebb-mind, the AI agent memory framework, via pipx or pip in seconds. Built-in SQLite (no external DB), optional PostgreSQL/pgvector, Docker, and a background service with Web Console and MCP."
---

# Installation

## Install (recommended: `pipx`)

```bash
pipx install hebb-mind
```

Requires **Python >= 3.10**. No external database needed — SQLite is built in.

`pipx` installs `hebb-mind` into its own isolated virtualenv and links the `hebb` / `hebb-mcp` entry points onto your `PATH` automatically. It's the modern default for Python CLI tools and avoids the two long-standing footguns of `pip install --user` (PATH not updated, PEP 668 on Homebrew / Debian-family Python).

### Install `pipx` if you don't have it

Run one block that matches your OS, then **open a new terminal** so the updated `PATH` takes effect.

::: code-group

```bash [macOS]
brew install pipx
pipx ensurepath
```

```bash [Debian / Ubuntu]
sudo apt install pipx       # Ubuntu 23.04+ / Debian 12+
pipx ensurepath
```

```bash [Fedora]
sudo dnf install pipx
pipx ensurepath
```

```powershell [Windows]
python -m pip install --user pipx
python -m pipx ensurepath
```

```bash [Any platform (fallback)]
python -m pip install --user pipx
python -m pipx ensurepath
```

:::

After `ensurepath` writes to your shell rc / Windows user `PATH`, open a new terminal and re-run `pipx install hebb-mind`.

To upgrade later: `pipx upgrade hebb-mind`. To remove cleanly: `pipx uninstall hebb-mind`.

### Alternative: virtualenv + `pip`

If you already work inside a virtualenv (or want to manage everything yourself):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U hebb-mind           # `hebb` lives on the venv's PATH
```

System-wide installs via `sudo pip install` work but are increasingly blocked by PEP 668 on modern distros; `pipx` is the supported path going forward.

## Setup

```bash
hebb setup
```

Creates `hebb.json` and `hebb.db` in the workspace, selects a **small** default embedding model from your OS locale, selects the download source, and downloads the model if it isn't already cached. The bare default is `all-MiniLM-L6-v2` (~90MB, English) or `intfloat/multilingual-e5-small` (~470MB, multilingual); add `--profile best` for the high-quality bge models (1–2GB). It does **not** start a background service.

By default the workspace is `~/.hebb/` (the global fallback). If you run `hebb setup` inside a directory that has — or will get — a `hebb.json`, that directory becomes the workspace instead. Resolution order: `$HEBB_HOME` → nearest ancestor `hebb.json` → `~/.hebb/`. Run `hebb config get workspace` to see the resolved location.

## Verify

```bash
hebb --version
hebb model status
```

## Install the background service

```bash
hebb service install
```

This registers Hebb Mind with launchd (macOS), systemd (Linux), or Task Scheduler (Windows) and starts it — per-user by default (no admin). Then open [http://localhost:8321/](http://localhost:8321/) for the Web Console, or [http://localhost:8321/docs](http://localhost:8321/docs) for the API docs.

## Docker

```bash
git clone https://github.com/afx-team/hebb-mind.git && cd hebb-mind
docker compose -f docker/docker-compose.yml up
```

## PostgreSQL Backend

For production workloads, switch to PostgreSQL + pgvector:

```bash
pipx install 'hebb-mind[pg]'    # or: pipx inject hebb-mind 'hebb-mind[pg]' --force
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

See [Storage Backends](../advanced/storage-backends.md) for details.

## Next Steps

- [Configuration](./configuration.md) — full config reference
- [Claude Code](./claude-code.md) — automatic cross-session memory for Claude Code
- [Codex](./codex.md) — MCP memory tools for Codex
- [MCP Integration](./mcp-integration.md) — use Hebb Mind as MCP tools in any client
