"""PostgreSQL + pgvector implementation of MemoryStore and PartitionStore."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import asyncpg

from hippocampus.constants import (
    DEFAULT_PARTITION_DESCRIPTIONS,
    DEFAULT_PARTITION_NAMES,
    SYSTEM_PARTITIONS,
)
from hippocampus.models.memory import Memory, MemoryCreate, MemoryMetadata, MemoryUpdate
from hippocampus.models.partition import Partition, PartitionCreate, PartitionUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _record_to_memory(row: asyncpg.Record) -> Memory:
    return Memory(
        id=row["id"],
        partition_id=row["partition_id"],
        content=row["content"],
        importance_score=row["importance_score"],
        tags=list(row["tags"]) if row["tags"] else [],
        metadata=MemoryMetadata(**(json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}))),
        source=row["source"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_accessed_at=row["last_accessed_at"],
        access_count=row["access_count"],
        expires_at=row["expires_at"],
    )


def _record_to_partition(row: asyncpg.Record) -> Partition:
    return Partition(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        enabled=row["enabled"],
        is_system=row["is_system"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PGMemoryStore:
    """PostgreSQL-backed memory store with pgvector for vector search."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self, data: MemoryCreate, embedding: list[float] | None = None
    ) -> Memory:
        memory_id = str(uuid.uuid4())
        now = _utcnow()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memories
                   (id, partition_id, content, importance_score, tags, metadata, source,
                    created_at, updated_at, last_accessed_at, access_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 0)""",
                memory_id, data.partition_id, data.content,
                data.importance_score, data.tags,
                json.dumps(data.metadata.model_dump(exclude_none=True)), data.source,
                now, now, now,
            )
            if embedding:
                pgvec = _to_pgvector(embedding)
                await conn.execute(
                    "INSERT INTO memory_embeddings (memory_id, embedding) VALUES ($1, $2)",
                    memory_id, pgvec,
                )
        return await self.get(memory_id)  # type: ignore[return-value]

    async def get(self, memory_id: str) -> Memory | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM memories WHERE id = $1",
                memory_id,
            )
        return _record_to_memory(row) if row else None

    async def list(
        self,
        partition_id: str | None = None,
        tags: list[str] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Memory], int]:
        conditions: list[str] = []
        params: list = []
        idx = 1

        if partition_id:
            conditions.append(f"partition_id = ${idx}")
            params.append(partition_id)
            idx += 1

        if tags:
            conditions.append(f"tags @> ${idx}")
            params.append(tags)
            idx += 1

        where = " AND ".join(conditions) if conditions else "TRUE"

        async with self.pool.acquire() as conn:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM memories WHERE {where}", *params)

            rows = await conn.fetch(
                f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
                *params, limit, offset,
            )

        memories = [_record_to_memory(r) for r in rows]
        return memories, total or 0

    async def update(self, memory_id: str, data: MemoryUpdate) -> Memory | None:
        existing = await self.get(memory_id)
        if not existing:
            return None

        sets = []
        params: list = []
        idx = 1

        if data.content is not None:
            sets.append(f"content = ${idx}")
            params.append(data.content)
            idx += 1
        if data.importance_score is not None:
            sets.append(f"importance_score = ${idx}")
            params.append(data.importance_score)
            idx += 1
        if data.tags is not None:
            sets.append(f"tags = ${idx}")
            params.append(data.tags)
            idx += 1
        if data.metadata is not None:
            sets.append(f"metadata = ${idx}")
            params.append(json.dumps(data.metadata.model_dump(exclude_none=True)))
            idx += 1

        if not sets:
            return existing

        sets.append(f"updated_at = ${idx}")
        params.append(_utcnow())
        idx += 1

        params.append(memory_id)
        set_clause = ", ".join(sets)

        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE memories SET {set_clause} WHERE id = ${idx}",
                *params,
            )
        return await self.get(memory_id)

    async def delete(self, memory_id: str) -> bool:
        async with self.pool.acquire() as conn:
            # Embedding cascade-deletes via FK
            result = await conn.execute(
                "DELETE FROM memories WHERE id = $1",
                memory_id,
            )
        return result == "DELETE 1"

    async def search_by_vector(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        if not query_embedding:
            return []
        pgvec = _to_pgvector(query_embedding)

        # Cosine distance: <=> returns distance in [0, 2]; similarity = 1 - distance/2
        if partition_ids:
            query = """
                SELECT m.*, (1 - (me.embedding <=> $1) / 2) AS similarity
                FROM memory_embeddings me
                JOIN memories m ON m.id = me.memory_id
                WHERE m.partition_id = ANY($2)
                ORDER BY me.embedding <=> $1
                LIMIT $3
            """
            params = [pgvec, partition_ids, top_k]
        else:
            query = """
                SELECT m.*, (1 - (me.embedding <=> $1) / 2) AS similarity
                FROM memory_embeddings me
                JOIN memories m ON m.id = me.memory_id
                ORDER BY me.embedding <=> $1
                LIMIT $2
            """
            params = [pgvec, top_k]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            memory = _record_to_memory(row)
            similarity = float(row["similarity"])
            results.append((memory, max(similarity, 0.0)))
        return results

    async def search_by_keyword(
        self,
        query: str,
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        """Full-text search using PostgreSQL tsvector with ts_rank_cd."""
        if not query.strip():
            return []

        if partition_ids:
            sql = """
                SELECT m.*, ts_rank_cd(m.content_tsv, plainto_tsquery('simple', $1)) AS rank
                FROM memories m
                WHERE m.content_tsv @@ plainto_tsquery('simple', $1)
                  AND m.partition_id = ANY($2)
                ORDER BY rank DESC
                LIMIT $3
            """
            params = [query, partition_ids, top_k]
        else:
            sql = """
                SELECT m.*, ts_rank_cd(m.content_tsv, plainto_tsquery('simple', $1)) AS rank
                FROM memories m
                WHERE m.content_tsv @@ plainto_tsquery('simple', $1)
                ORDER BY rank DESC
                LIMIT $2
            """
            params = [query, top_k]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = []
        for row in rows:
            memory = _record_to_memory(row)
            similarity = min(float(row["rank"]), 1.0)
            results.append((memory, max(similarity, 0.0)))
        return results

    async def get_by_partition(self, partition_id: str) -> list[Memory]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM memories WHERE partition_id = $1 ORDER BY created_at DESC",
                partition_id,
            )
        return [_record_to_memory(r) for r in rows]

    async def delete_expired(self) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < now()",
            )
        # result is like "DELETE 5"
        return int(result.split()[-1]) if result else 0

    async def update_access(self, memory_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = now() WHERE id = $1",
                memory_id,
            )

    async def update_embedding(self, memory_id: str, embedding: list[float]) -> None:
        if not embedding:
            return
        pgvec = _to_pgvector(embedding)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memory_embeddings (memory_id, embedding) VALUES ($1, $2)
                   ON CONFLICT (memory_id) DO UPDATE SET embedding = EXCLUDED.embedding""",
                memory_id, pgvec,
            )

    async def update_expiry(self, memory_id: str, expires_at: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE memories SET expires_at = $1 WHERE id = $2",
                datetime.fromisoformat(expires_at), memory_id,
            )


class PGPartitionStore:
    """PostgreSQL-backed partition store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self, data: PartitionCreate, is_system: bool = False
    ) -> Partition:
        now = _utcnow()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO partitions (id, name, description, enabled, is_system, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                data.id, data.name, data.description, data.enabled, is_system, now, now,
            )
        return await self.get(data.id)  # type: ignore[return-value]

    async def get(self, partition_id: str) -> Partition | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM partitions WHERE id = $1",
                partition_id,
            )
            if not row:
                return None
            partition = _record_to_partition(row)
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM memories WHERE partition_id = $1",
                partition_id,
            )
            partition.memory_count = count or 0
        return partition

    async def list(self) -> list[Partition]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM partitions ORDER BY created_at"
            )
            partitions = []
            for row in rows:
                p = _record_to_partition(row)
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM memories WHERE partition_id = $1",
                    p.id,
                )
                p.memory_count = count or 0
                partitions.append(p)
        return partitions

    async def update(
        self, partition_id: str, data: PartitionUpdate
    ) -> Partition | None:
        existing = await self.get(partition_id)
        if not existing:
            return None

        sets = []
        params: list = []
        idx = 1

        if data.name is not None:
            sets.append(f"name = ${idx}")
            params.append(data.name)
            idx += 1
        if data.description is not None:
            sets.append(f"description = ${idx}")
            params.append(data.description)
            idx += 1
        if data.enabled is not None:
            sets.append(f"enabled = ${idx}")
            params.append(data.enabled)
            idx += 1

        if not sets:
            return existing

        sets.append(f"updated_at = ${idx}")
        params.append(_utcnow())
        idx += 1

        params.append(partition_id)
        set_clause = ", ".join(sets)

        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE partitions SET {set_clause} WHERE id = ${idx}",
                *params,
            )
        return await self.get(partition_id)

    async def delete(self, partition_id: str) -> bool:
        existing = await self.get(partition_id)
        if not existing or existing.is_system:
            return False
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM partitions WHERE id = $1",
                partition_id,
            )
        return True

    async def ensure_defaults(self) -> None:
        """Create all default system partitions if they don't exist."""
        now = _utcnow()
        async with self.pool.acquire() as conn:
            for pt in SYSTEM_PARTITIONS:
                await conn.execute(
                    """INSERT INTO partitions
                       (id, name, description, enabled, is_system, created_at, updated_at)
                       VALUES ($1, $2, $3, TRUE, TRUE, $4, $5)
                       ON CONFLICT (id) DO NOTHING""",
                    pt.value, DEFAULT_PARTITION_NAMES[pt], DEFAULT_PARTITION_DESCRIPTIONS[pt],
                    now, now,
                )


def _to_pgvector(embedding: list[float]) -> str:
    """Convert a list of floats to pgvector string format: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(x) for x in embedding) + "]"
