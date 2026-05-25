# Installation

## Install

```bash
pip install --user -U hebb-mind
```

Requires **Python >= 3.10**. No external database needed — SQLite is built in.

### PATH setup (`pip install --user` only)

On macOS the Python user-script directory is **not on `PATH`** by default. After `pip install --user`, `hebb` will be `command not found` until you add it. This is a one-time setup — pick the line for your shell:

```bash
# zsh (macOS default)
echo 'export PATH="$(python3 -m site --user-base)/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

# bash
echo 'export PATH="$(python3 -m site --user-base)/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc

# fish
fish_add_path (python3 -m site --user-base)/bin
```

`python3 -m site --user-base` prints the directory pip used (typically `~/Library/Python/3.x` on macOS, `~/.local` on Linux). You can verify with `python3 -m site --user-base`.

You can skip this step entirely by installing inside a virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U hebb-mind   # `hebb` is on the venv's PATH automatically
```

Or system-wide (requires `sudo` on most setups):

```bash
sudo pip install -U hebb-mind
```

## Setup

```bash
hebb setup
```

Creates `hebb.json` and `hebb.db`, selects the default embedding model, selects the download source, and verifies the model. It does **not** start a background service.

## Verify

```bash
hebb --version
hebb model status
hebb service install
```

Open [http://localhost:8321/](http://localhost:8321/) for the Web Console, or [http://localhost:8321/docs](http://localhost:8321/docs) for the API docs.

## Docker

```bash
git clone https://github.com/afx-team/hebb-mind.git && cd hebb-mind
docker compose -f docker/docker-compose.yml up
```

## PostgreSQL Backend

For production workloads, switch to PostgreSQL + pgvector:

```bash
pip install hebb-mind[pg]
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

See [Storage Backends](../advanced/storage-backends.md) for details.

## Next Steps

- [Configuration](./configuration.md) — full config reference
- [Claude Code](./claude-code.md) — automatic cross-session memory for Claude Code
- [Codex](./codex.md) — MCP memory tools for Codex
- [MCP Integration](./mcp-integration.md) — use Hebb Mind as MCP tools in any client
