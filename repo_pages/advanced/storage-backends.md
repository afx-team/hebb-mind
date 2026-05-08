# Storage Backends

Hippocampus supports two storage backends: SQLite (default) and PostgreSQL with pgvector.

## SQLite (Default)

SQLite is the default backend, requiring zero configuration. All data is stored in a single file in the workspace directory.

```bash
hippocampus config set storage_type sqlite
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
pip install afx-hippocampus[pg]
```

Configure the connection:

```bash
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
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
hippocampus config set pg_pool_min 2

# Maximum connections in the pool
hippocampus config set pg_pool_max 10
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

Hippocampus handles schema creation and migrations automatically on first connection.

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
  -v hippocampus-data:/root/.hippocampus \
  -e HIPPOCAMPUS_LLM_API_KEY=sk-your-key \
  ghcr.io/afx-team/hippocampus:latest
```

### Docker Compose

```yaml
services:
  hippocampus:
    image: ghcr.io/afx-team/hippocampus:latest
    ports:
      - "8321:8321"
    volumes:
      - hippocampus-data:/root/.hippocampus
    environment:
      - HIPPOCAMPUS_HOME=/root/.hippocampus
      - HIPPOCAMPUS_LLM_API_KEY=${LLM_API_KEY}
      - HIPPOCAMPUS_LLM_MODEL=openai/gpt-4o-mini

  # Optional: PostgreSQL backend
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: hippocampus
      POSTGRES_USER: hippocampus
      POSTGRES_PASSWORD: hippocampus
    volumes:
      - pg-data:/var/lib/postgresql/data

volumes:
  hippocampus-data:
  pg-
```

### Environment Variables

| Variable | Config Key | Description |
|----------|-----------|-------------|
| `HIPPOCAMPUS_HOME` | `home` | Workspace directory (overrides config file location and `home` field) |
| `HIPPOCAMPUS_LLM_API_KEY` | `llm_api_key` | LLM provider API key |
| `HIPPOCAMPUS_LLM_MODEL` | `llm_model` | Model identifier (via LiteLLM) |
| `HIPPOCAMPUS_LLM_BASE_URL` | `llm_base_url` | Custom API endpoint |
| `HIPPOCAMPUS_STORAGE_TYPE` | `storage_type` | `sqlite` or `postgresql` |
| `HIPPOCAMPUS_PG_URL` | `pg_url` | PostgreSQL connection string |
| `HIPPOCAMPUS_PORT` | `port` | Server port (default 8321) |

## Running as a Background Service

`hippocampus start` runs in the foreground by default. For long-running deployments, use one of these approaches:

### nohup (Quick)

```bash
nohup hippocampus start > hippocampus.log 2>&1 &
```

### systemd (Linux)

Create `/etc/systemd/system/hippocampus.service`:

```ini
[Unit]
Description=Hippocampus Memory Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
ExecStart=/path/to/hippocampus start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable hippocampus   # auto-start on boot
sudo systemctl start hippocampus    # start now
sudo systemctl status hippocampus   # check status
```

### launchd (macOS)

Create `~/Library/LaunchAgents/com.hippocampus.server.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hippocampus.server</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/hippocampus</string>
    <string>start</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/project</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/hippocampus.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/hippocampus.err</string>
</dict>
</plist>
```

Load and start:

```bash
launchctl load ~/Library/LaunchAgents/com.hippocampus.server.plist
```

Unload to stop:

```bash
launchctl unload ~/Library/LaunchAgents/com.hippocampus.server.plist
```

## Running as a Background Service

For daemon mode and auto-start on boot, see [Quick Start → Keep It Running](../quick-start.md#keep-it-running).

### Production Tips

- Use PostgreSQL backend for production workloads
- Set `HIPPOCAMPUS_LLM_BASE_URL` for Chinese model providers (Qwen, GLM, Kimi)
- Mount a persistent volume for the workspace directory (`/root/.hippocampus` by default) to preserve memories across restarts
- Use `--restart unless-stopped` for automatic recovery
