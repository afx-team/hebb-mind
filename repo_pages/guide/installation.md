# Installation

## Install

```bash
pip install -U afx-hippocampus
```

Requires **Python >= 3.10**. No external database needed — SQLite is built in.

## Setup

```bash
hippocampus setup
```

Creates `hippocampus.json` and `hippocampus.db`, selects the default embedding model, selects the download source, and verifies the model. It does **not** start a background service.

For scripted or offline initialization only:

```bash
hippocampus init
```

## Verify

```bash
hippocampus --version
hippocampus model status
hippocampus start
```

Open [http://localhost:8321/](http://localhost:8321/) for the Web Console, or [http://localhost:8321/docs](http://localhost:8321/docs) for the API docs.

## Docker

```bash
git clone https://github.com/afx-team/hippocampus.git && cd hippocampus
docker compose -f docker/docker-compose.yml up
```

## PostgreSQL Backend

For production workloads, switch to PostgreSQL + pgvector:

```bash
pip install afx-hippocampus[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```

See [Storage Backends](../advanced/storage-backends.md) for details.

## Next Steps

- [Configuration](./configuration.md) — full config reference
- [Claude Code](./claude-code.md) — automatic cross-session memory for Claude Code
- [Codex](./codex.md) — MCP memory tools for Codex
- [MCP Integration](./mcp-integration.md) — use hippocampus as MCP tools in any client
