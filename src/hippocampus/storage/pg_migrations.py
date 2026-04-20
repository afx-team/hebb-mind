"""PostgreSQL schema initialization with pgvector extension."""

from __future__ import annotations

import asyncpg


async def initialize_pg_schema(pool: asyncpg.Pool, embedding_dim: int = 384) -> None:
    """Create all tables and indexes idempotently."""
    async with pool.acquire() as conn:
        # Enable pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS partitions (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                enabled     BOOLEAN NOT NULL DEFAULT TRUE,
                is_system   BOOLEAN NOT NULL DEFAULT FALSE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id                TEXT PRIMARY KEY,
                partition_id      TEXT NOT NULL,
                content           TEXT NOT NULL,
                importance_score  DOUBLE PRECISION NOT NULL DEFAULT 5.0,
                tags              TEXT[] NOT NULL DEFAULT '{}',
                metadata          JSONB NOT NULL DEFAULT '{}',
                source            TEXT,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_accessed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                access_count      INTEGER NOT NULL DEFAULT 0,
                expires_at        TIMESTAMPTZ
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_partition ON memories(partition_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_expires_at ON memories(expires_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING GIN(tags)")

        # Embeddings table with pgvector
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_id   TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
                embedding   vector({int(embedding_dim)}) NOT NULL
            )
        """)

        # IVFFlat index for fast ANN search (only if enough rows exist; create always, PG handles it)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_ivfflat
            ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        # Full-text search: tsvector column + GIN index + auto-update trigger
        # Uses 'simple' config for cross-language compatibility (no zhparser needed)
        await conn.execute("ALTER TABLE memories ADD COLUMN IF NOT EXISTS content_tsv tsvector")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_fts ON memories USING GIN(content_tsv)")
        await conn.execute("""
            CREATE OR REPLACE FUNCTION memories_tsv_trigger() RETURNS trigger AS $$
            BEGIN NEW.content_tsv := to_tsvector('simple', NEW.content); RETURN NEW; END;
            $$ LANGUAGE plpgsql
        """)
        await conn.execute("DROP TRIGGER IF EXISTS trg_memories_tsv ON memories")
        await conn.execute("""
            CREATE TRIGGER trg_memories_tsv BEFORE INSERT OR UPDATE ON memories
            FOR EACH ROW EXECUTE FUNCTION memories_tsv_trigger()
        """)
        # Backfill existing rows
        await conn.execute("UPDATE memories SET content_tsv = to_tsvector('simple', content) WHERE content_tsv IS NULL")
