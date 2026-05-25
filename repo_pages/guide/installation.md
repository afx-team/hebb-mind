# Installation

## Install

```bash
pip install -U hebb-mind
```

Requires **Python >= 3.10**. No external database needed — SQLite is built in.

## Setup

```bash
hebb setup
```

Creates `hebb.json` and `hebb.db`, selects the default embedding model, selects the download source, and verifies the model. It does **not** start a background service.

For scripted or offline initialization only:

```bash
hebb init
```

## Verify

```bash
hebb --version
hebb model status
hebb start
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
