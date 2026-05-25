# Storage Backends

Hebb Mind supports two storage backends: SQLite (default) and PostgreSQL with pgvector.

## SQLite (Default)

SQLite is the default backend, requiring zero configuration. All data is stored in a single file in the workspace directory.

```bash
hebb config set storage_type sqlite
```

### Features

- **Zero-config** -- no external database server required
- **Single file** -- the entire database is one `.db` file, easy to back up or move
- **sqlite-vec** -- extension for vector similarity search
- **FTS5** -- built-in full-text search with BM25 ranking

### When to Use

- Personal use and development
- Single-user deployments
- Prototyping and testing
- Environments where you cannot run a database server

### Limitations

- Single-writer concurrency (reads are concurrent)
- Not ideal for multi-process or distributed deployments
- Vector search performance may degrade with very large datasets (1M+ memories)

## PostgreSQL + pgvector

PostgreSQL provides production-grade storage with native vector types, connection pooling, and full concurrent access.

### Setup

Install the PostgreSQL extras:

```bash
pip install hebb-mind[pg]
```

Configure the connection:

```bash
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

### Features

- **pgvector** -- native vector data type and indexing for high-performance similarity search
- **tsvector + GIN** -- built-in full-text search with ranking
- **Connection pooling** -- configurable pool size for concurrent access
- **ACID transactions** -- full transactional integrity
- **Scalability** -- handles millions of memories efficiently

### Connection Pool Configuration

```bash
# Minimum connections in the pool
hebb config set pg_pool_min 2

# Maximum connections in the pool
hebb config set pg_pool_max 10
```

### When to Use

- Production deployments
- Multi-user or multi-agent environments
- High-concurrency workloads
- Large memory stores (100K+ memories)
- When you need backup, replication, or monitoring from PostgreSQL tooling

### PostgreSQL Setup

Ensure pgvector is installed in your PostgreSQL instance:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Hebb Mind handles schema creation and migrations automatically on first connection.

## Comparison

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Setup complexity | None | Requires server |
| Vector search | sqlite-vec | pgvector |
| Full-text search | FTS5 | tsvector + GIN |
| Concurrency | Single-writer | Full concurrent |
| Connection pooling | N/A | Configurable |
| Scalability | Moderate | High |
| Backup | Copy file | pg_dump / replication |
| Best for | Development, personal use | Production, multi-user |

## Switching Backends

Switching between backends requires migrating your data. Currently, this must be done manually:

1. Export memories via the API (`GET /api/v1/memories`)
2. Change the storage backend configuration
3. Restart the server (schema is created automatically)
4. Re-import memories via the batch API (`POST /api/v1/memories/batch`)

## Docker Deployment

For containerized deployments, use the official Docker image.

### Quick Start

```bash
docker run -d \
  -p 8321:8321 \
  -v hebb-data:/data \
  -e HEBB_HOME=/data \
  -e HEBB_LANGUAGE=auto \
  -e HEBB_REGION=auto \
  -e HEBB_LLM_API_KEY=sk-your-key \
  ghcr.io/afx-team/hebb-mind:latest
```

### Docker Compose

```yaml
services:
  hebb:
    image: ghcr.io/afx-team/hebb-mind:latest
    ports:
      - "8321:8321"
    volumes:
      - hebb-data:/data
    environment:
      - HEBB_HOME=/data
      - HEBB_LANGUAGE=auto
      - HEBB_REGION=auto
      - HEBB_LLM_API_KEY=${LLM_API_KEY}
      - HEBB_LLM_MODEL=openai/gpt-4o-mini

  # Optional: PostgreSQL backend
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: hebb
      POSTGRES_USER: hebb
      POSTGRES_PASSWORD: hebb
    volumes:
      - pg-data:/var/lib/postgresql/data

volumes:
  hebb-data:
  pg-data:
```

### Environment Variables

| Variable | Config Key | Description |
|----------|-----------|-------------|
| `HEBB_HOME` | `home` | Workspace directory (overrides config file location and `home` field) |
| `HEBB_LANGUAGE` | setup option | `auto`, `en`, `zh`, or `multi`; selects the default embedding model during container setup |
| `HEBB_REGION` | setup option | `auto`, `cn`, or `global`; selects the model download source during container setup |
| `HEBB_LLM_API_KEY` | `llm_api_key` | LLM provider API key |
| `HEBB_LLM_MODEL` | `llm_model` | Model identifier (via LiteLLM) |
| `HEBB_LLM_BASE_URL` | `llm_base_url` | Custom API endpoint |
| `HEBB_STORAGE_TYPE` | `storage_type` | `sqlite` or `postgresql` |
| `HEBB_PG_URL` | `pg_url` | PostgreSQL connection string |
| `HEBB_PORT` | `port` | Server port (default 8321) |

## Running as a Background Service

Hebb Mind always runs as an OS-managed background service. The single
supported entry point is:

```bash
hebb service install     # registers + starts (launchd / systemd / Task Scheduler)
hebb service uninstall   # removes it
```

`install` writes the platform-native artifact for you and immediately
starts the service. Defaults to **per-user** scope (no admin/sudo
needed); pass `--scope system` for a system-wide install.

| Platform | Artifact written by `hebb service install` (default `--scope user`) |
|----------|---------------------------------------------------------------------|
| macOS    | `~/Library/LaunchAgents/com.hebb.server.plist` (launchd LaunchAgent) |
| Linux    | `~/.config/systemd/user/hebb.service` (`systemctl --user` unit) |
| Windows  | Per-user Scheduled Task `HebbMind` (interactive logon trigger, `LeastPrivilege`) |

`--scope system` writes to `/Library/LaunchDaemons/`,
`/etc/systemd/system/`, or registers a SYSTEM-account Scheduled Task,
respectively — all of which need elevation and run at boot for all users.

The actual server process invoked by the service manager is `hebb _serve`
(an internal foreground entrypoint that's not part of the public CLI).
See [CLI Reference → hebb service](../api/cli.md#hebb-service) for the
control commands and platform-specific log paths.

### Production Tips

- Use PostgreSQL backend for production workloads
- Set `HEBB_LLM_BASE_URL` for Chinese model providers (Qwen, GLM, Kimi)
- Mount a persistent volume for the workspace directory (`/root/.hebb` by default) to preserve memories across restarts
- Use `--restart unless-stopped` for automatic recovery
