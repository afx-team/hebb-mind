# Storage Backends

Hippocampus supports two storage backends: SQLite (default) and PostgreSQL with pgvector.

## SQLite (Default)

SQLite is the default backend, requiring zero configuration. All data is stored in a single file.

```bash
hippocampus config set storage_type sqlite
hippocampus config set db_path hippocampus.db
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
