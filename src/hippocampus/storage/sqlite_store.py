"""SQLite + sqlite-vec implementation of MemoryStore."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite
import numpy as np

from hippocampus.models.memory import Memory, MemoryCreate, MemoryMetadata, MemoryUpdate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_memory(row: aiosqlite.Row) -> Memory:
    return Memory(
        id=row["id"],
        partition_id=row["partition_id"],
        content=row["content"],
        importance_score=row["importance_score"],
        tags=json.loads(row["tags"]),
        metadata=MemoryMetadata(**json.loads(row["metadata"])),
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
        access_count=row["access_count"],
        expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
    )


class SQLiteMemoryStore:
    """SQLite-backed memory store with sqlite-vec for vector search."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(self, data: MemoryCreate, embedding: list[float] | None = None) -> Memory:
        memory_id = str(uuid.uuid4())
        now = _now_iso()
        await self.db.execute(
            """INSERT INTO memories
               (id, partition_id, content, importance_score, tags, metadata, source,
                created_at, updated_at, last_accessed_at, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                memory_id,
                data.partition_id,
                data.content,
                data.importance_score,
                json.dumps(data.tags),
                json.dumps(data.metadata.model_dump(exclude_none=True)),
                data.source,
                now,
                now,
                now,
            ),
        )
        if embedding:
            vec_bytes = np.array(embedding, dtype=np.float32).tobytes()
            await self.db.execute(
                "INSERT INTO memory_embeddings (memory_id, embedding) VALUES (?, ?)",
                (memory_id, vec_bytes),
            )
        # FTS5 index for keyword search
        await self.db.execute(
            "INSERT INTO memory_fts (memory_id, content) VALUES (?, ?)",
            (memory_id, data.content),
        )
        await self.db.commit()
        return await self.get(memory_id)  # type: ignore[return-value]

    async def get(self, memory_id: str) -> Memory | None:
        cursor = await self.db.execute(
            "SELECT * FROM memories WHERE id = ?",
            (memory_id,),
        )
        row = await cursor.fetchone()
        return _row_to_memory(row) if row else None

    async def list(
        self,
        partition_id: str | None = None,
        tags: list[str] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Memory], int]:
        conditions: list[str] = []
        params: list = []

        if partition_id:
            conditions.append("partition_id = ?")
            params.append(partition_id)

        where = " AND ".join(conditions) if conditions else "1=1"

        # Count
        cursor = await self.db.execute(f"SELECT COUNT(*) FROM memories WHERE {where}", params)
        row = await cursor.fetchone()
        total = row[0] if row else 0

        # Fetch
        cursor = await self.db.execute(
            f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        rows = await cursor.fetchall()
        memories = [_row_to_memory(r) for r in rows]

        # Tag filtering (post-query since tags are JSON)
        if tags:
            tag_set = set(tags)
            memories = [m for m in memories if tag_set.intersection(m.tags)]
            total = len(memories)

        return memories, total

    async def update(self, memory_id: str, data: MemoryUpdate) -> Memory | None:
        existing = await self.get(memory_id)
        if not existing:
            return None

        updates = []
        params: list = []
        if data.content is not None:
            updates.append("content = ?")
            params.append(data.content)
        if data.importance_score is not None:
            updates.append("importance_score = ?")
            params.append(data.importance_score)
        if data.tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(data.tags))
        if data.metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(data.metadata.model_dump(exclude_none=True)))

        if not updates:
            return existing

        updates.append("updated_at = ?")
        params.append(_now_iso())
        params.append(memory_id)

        await self.db.execute(
            f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        # Sync FTS5 if content changed
        if data.content is not None:
            await self.db.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            await self.db.execute(
                "INSERT INTO memory_fts (memory_id, content) VALUES (?, ?)",
                (memory_id, data.content),
            )
        await self.db.commit()
        return await self.get(memory_id)

    async def delete(self, memory_id: str) -> bool:
        cursor = await self.db.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,),
        )
        await self.db.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
        await self.db.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
        await self.db.commit()
        return cursor.rowcount > 0

    async def search_by_vector(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        if not query_embedding:
            return []
        vec_bytes = np.array(query_embedding, dtype=np.float32).tobytes()

        # sqlite-vec KNN query (requires vec0 virtual table)
        try:
            cursor = await self.db.execute(
                """SELECT me.memory_id, me.distance
                   FROM memory_embeddings me
                   WHERE me.embedding MATCH ? AND k = ?
                   ORDER BY me.distance""",
                (vec_bytes, top_k * 3),  # over-fetch for filtering
            )
        except Exception:
            # vec0 not available — fallback table does not support MATCH
            return []
        rows = await cursor.fetchall()

        results = []
        for row in rows:
            memory = await self.get(row["memory_id"])
            if not memory:
                continue
            if partition_ids and memory.partition_id not in partition_ids:
                continue
            # sqlite-vec returns L2 distance; convert to similarity [0, 1]
            distance = row["distance"]
            similarity = 1.0 / (1.0 + distance)
            results.append((memory, similarity))
            if len(results) >= top_k:
                break

        return results

    async def search_by_keyword(
        self,
        query: str,
        top_k: int = 10,
        partition_ids: list[str] | None = None,
    ) -> list[tuple[Memory, float]]:
        """Full-text search using FTS5 with BM25 ranking."""
        if not query.strip():
            return []

        # FTS5 MATCH query; bm25() returns negative scores (lower = more relevant)
        try:
            cursor = await self.db.execute(
                """SELECT f.memory_id, bm25(memory_fts) AS rank
                   FROM memory_fts f
                   WHERE memory_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, top_k * 3),
            )
        except Exception:
            # FTS table may not exist or query syntax invalid
            return []

        rows = await cursor.fetchall()
        results = []
        for row in rows:
            memory = await self.get(row["memory_id"])
            if not memory:
                continue
            if partition_ids and memory.partition_id not in partition_ids:
                continue
            # bm25 returns negative; convert to [0, 1] similarity
            similarity = 1.0 / (1.0 + abs(row["rank"]))
            results.append((memory, similarity))
            if len(results) >= top_k:
                break
        return results

    async def get_by_partition(self, partition_id: str) -> list[Memory]:
        cursor = await self.db.execute(
            "SELECT * FROM memories WHERE partition_id = ? ORDER BY created_at DESC",
            (partition_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_memory(r) for r in rows]

    async def delete_expired(self) -> list[str]:
        now = _now_iso()
        # Get expired memory IDs first (for embedding/fts cleanup)
        cursor = await self.db.execute(
            "SELECT id FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        rows = await cursor.fetchall()
        expired_ids = [row["id"] for row in rows]

        if not expired_ids:
            return []

        placeholders = ",".join("?" * len(expired_ids))
        await self.db.execute(
            f"DELETE FROM memory_embeddings WHERE memory_id IN ({placeholders})",
            expired_ids,
        )
        await self.db.execute(
            f"DELETE FROM memory_fts WHERE memory_id IN ({placeholders})",
            expired_ids,
        )
        await self.db.execute(
            f"DELETE FROM memories WHERE id IN ({placeholders})",
            expired_ids,
        )
        await self.db.commit()
        return expired_ids

    async def update_access(self, memory_id: str) -> None:
        await self.db.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
            (_now_iso(), memory_id),
        )
        await self.db.commit()

    async def update_embedding(self, memory_id: str, embedding: list[float]) -> None:
        if not embedding:
            return
        vec_bytes = np.array(embedding, dtype=np.float32).tobytes()
        await self.db.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
        await self.db.execute(
            "INSERT INTO memory_embeddings (memory_id, embedding) VALUES (?, ?)",
            (memory_id, vec_bytes),
        )
        await self.db.commit()

    async def update_expiry(self, memory_id: str, expires_at: str) -> None:
        await self.db.execute(
            "UPDATE memories SET expires_at = ? WHERE id = ?",
            (expires_at, memory_id),
        )
        await self.db.commit()
