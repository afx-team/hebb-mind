"""SQLite + sqlite-vec implementation of MemoryStore."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
import numpy as np

from hebb.models.memory import Memory, MemoryCreate, MemoryMetadata, MemoryUpdate
from hebb.retrieval.fts_query import build_fts_query

logger = logging.getLogger(__name__)

# See `hebb.storage.base` — alias the builtin so class-scope annotations
# don't resolve to the `list` method defined below.
_List = list

# Matches the declared vec0 embedding width, e.g. ``embedding float[384]``,
# inside the CREATE VIRTUAL TABLE SQL recorded in ``sqlite_master``.
_VEC_DIM_RE = re.compile(r"embedding\s+float\[(\d+)\]", re.IGNORECASE)


class EmbeddingDimensionError(ValueError):
    """Raised when an embedding's length does not match the vec0 table width.

    Surfaced before the vec0 INSERT so the whole ``create`` rolls back cleanly
    instead of letting a raw vec0 error abort a partially-written row.
    """


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

    def __init__(self, db: aiosqlite.Connection, write_lock: asyncio.Lock | None = None) -> None:
        self.db = db
        # Process-level write lock shared with KnowledgeGraph and
        # PartitionStore (Issue #36). When provided by the factory, a single
        # ``asyncio.Lock`` serialises every SQL mutation *and* its
        # corresponding graph mutation so the two form one crash-consistent
        # unit. When ``None`` (tests, standalone usage) a standalone lock is
        # created. The ``_*_impl`` methods skip lock acquisition so callers
        # that already hold the lock can compose multiple operations in one
        # critical section without deadlocking on ``asyncio.Lock``
        # non-reentrancy.
        self._write_lock = write_lock or asyncio.Lock()
        # Declared vec0 embedding width, read lazily from the schema and cached.
        # ``None`` means the dimension is unknown (e.g. the regular-table
        # fallback when vec0 is unavailable), in which case the guard is skipped.
        self._vec_dim: int | None = None
        self._vec_dim_loaded = False

    async def _begin(self) -> None:
        """Open an explicit immediate transaction.

        ``BEGIN IMMEDIATE`` takes the write lock up front so the multi-statement
        body either commits as a unit or rolls back. aiosqlite runs in autocommit
        (``isolation_level=None``) under the hood, so an explicit BEGIN is what
        gives us a real transaction boundary.
        """
        await self.db.execute("BEGIN IMMEDIATE")

    async def _get_vec_dim(self) -> int | None:
        """Declared vec0 embedding width, or ``None`` if it can't be determined.

        Returns:
            The integer dimension parsed from the ``memory_embeddings`` CREATE
            statement, or ``None`` when the table is absent or is the
            regular-BLOB fallback (which has no fixed width).
        """
        if self._vec_dim_loaded:
            return self._vec_dim
        try:
            cursor = await self.db.execute("SELECT sql FROM sqlite_master WHERE name = 'memory_embeddings'")
            row = await cursor.fetchone()
        except Exception:  # pragma: no cover - sqlite_master is always present
            row = None
        if row and row[0]:
            match = _VEC_DIM_RE.search(row[0])
            if match:
                self._vec_dim = int(match.group(1))
        self._vec_dim_loaded = True
        return self._vec_dim

    async def create(self, data: MemoryCreate, embedding: _List[float] | None = None) -> Memory:
        """Insert a memory row + (optional) embedding + FTS5 index in one transaction.

        Args:
            data: Memory fields to insert.
            embedding: Optional embedding vector; length must match the declared
                vec0 width or an ``EmbeddingDimensionError`` is raised (rolled back).

        Returns:
            The freshly created ``Memory`` (re-read by id so timestamps + defaults
            reflect what landed in the row).
        """
        async with self._write_lock:
            return await self._create_impl(data, embedding)

    async def _create_impl(
        self, data: MemoryCreate, embedding: _List[float] | None = None, *, skip_tx: bool = False
    ) -> Memory:
        """``create`` without lock acquisition — for callers already holding ``_write_lock``.

        Args:
            skip_tx: When ``True``, skip the internal ``BEGIN IMMEDIATE … COMMIT``
                boundary. The caller is responsible for wrapping this call in an
                explicit transaction so multiple SQL operations form one atomic unit.
        """
        memory_id = str(uuid.uuid4())
        now = _now_iso()
        vec_bytes: bytes | None = None
        if embedding:
            expected = await self._get_vec_dim()
            if expected is not None and len(embedding) != expected:
                raise EmbeddingDimensionError(f"embedding length {len(embedding)} does not match vec0 width {expected}")
            vec_bytes = np.array(embedding, dtype=np.float32).tobytes()

        if not skip_tx:
            await self._begin()
        try:
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
            if vec_bytes is not None:
                await self.db.execute(
                    "INSERT INTO memory_embeddings (memory_id, partition_id, embedding) VALUES (?, ?, ?)",
                    (memory_id, data.partition_id, vec_bytes),
                )
            # FTS5 index for keyword search — partition_id is UNINDEXED but
            # carried so retrieval can filter by partition inside MATCH.
            await self.db.execute(
                "INSERT INTO memory_fts (memory_id, partition_id, content) VALUES (?, ?, ?)",
                (memory_id, data.partition_id, data.content),
            )
            if not skip_tx:
                await self.db.commit()
        except BaseException:
            if not skip_tx:
                await self.db.rollback()
            raise
        return await self.get(memory_id)  # type: ignore[return-value]

    async def get(self, memory_id: str) -> Memory | None:
        """Fetch a single memory by id, or ``None`` if no row matches."""
        cursor = await self.db.execute(
            "SELECT * FROM memories WHERE id = ?",
            (memory_id,),
        )
        row = await cursor.fetchone()
        return _row_to_memory(row) if row else None

    async def list(
        self,
        partition_id: str | None = None,
        tags: _List[str] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[_List[Memory], int]:
        """List memories optionally filtered by partition and tags, newest-first.

        Args:
            partition_id: When provided, restricts the result to one partition.
            tags: When provided, keeps only memories whose tags intersect the set
                (post-query JSON filter — not a SQL predicate, so the returned
                ``total`` is the surviving count, not the pre-filter count).
            offset: Result offset (LIMIT/OFFSET on the SQL side).
            limit: Maximum rows to return.

        Returns:
            A ``(rows, total)`` pair sorted by ``created_at`` descending.
        """
        conditions: _List[str] = []
        params: _List[Any] = []

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
        """Apply the non-None ``data`` fields in one transaction under the write lock.

        Syncs the FTS5 index when ``content`` changed. Returns the updated memory
        or ``None`` if no row matches ``memory_id`` (or if ``data`` carried no
        fields to apply, in which case the existing row is returned unchanged).
        """
        async with self._write_lock:
            return await self._update_impl(memory_id, data)

    async def _update_impl(self, memory_id: str, data: MemoryUpdate) -> Memory | None:
        """``update`` without lock acquisition — for callers already holding ``_write_lock``."""
        existing = await self.get(memory_id)
        if not existing:
            return None

        updates: _List[str] = []
        params: _List[Any] = []
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

        await self._begin()
        try:
            await self.db.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            # Sync FTS5 if content changed
            if data.content is not None:
                await self.db.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
                await self.db.execute(
                    "INSERT INTO memory_fts (memory_id, partition_id, content) VALUES (?, ?, ?)",
                    (memory_id, existing.partition_id, data.content),
                )
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise
        return await self.get(memory_id)

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory row + its embedding row + its FTS5 row in one transaction.

        Returns ``True`` if the base row existed (and was deleted), ``False``
        if no row matched ``memory_id``. The embedding/FTS cleanup runs
        unconditionally so a stale auxiliary row is swept even when the base row
        was already gone.
        """
        async with self._write_lock:
            return await self._delete_impl(memory_id)

    async def _delete_impl(self, memory_id: str, *, skip_tx: bool = False) -> bool:
        """``delete`` without lock acquisition — for callers already holding ``_write_lock``.

        Args:
            skip_tx: When ``True``, skip the internal ``BEGIN IMMEDIATE … COMMIT``
                boundary. The caller is responsible for wrapping this call in an
                explicit transaction so multiple SQL operations form one atomic unit.
        """
        if not skip_tx:
            await self._begin()
        try:
            cursor = await self.db.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )
            deleted = cursor.rowcount > 0
            await self.db.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
            await self.db.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            if not skip_tx:
                await self.db.commit()
        except BaseException:
            if not skip_tx:
                await self.db.rollback()
            raise
        return deleted

    async def search_by_vector(
        self,
        query_embedding: _List[float],
        top_k: int = 10,
        partition_ids: _List[str] | None = None,
    ) -> _List[tuple[Memory, float]]:
        """Partition-aware vector KNN.

        ``partition_id`` is a metadata column on the vec0 virtual table,
        so the partition filter pushes into MATCH itself — no global
        KNN + post-filter, no vec0 4096-row cap, no per-row ``get()``
        fan-out. KNN is scoped to the requested partitions from the
        start; we ask for ``top_k * 3`` candidates and trust the index.
        """
        if not query_embedding:
            return []
        vec_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
        k = top_k * 3

        try:
            if partition_ids:
                placeholders = ",".join("?" * len(partition_ids))
                cursor = await self.db.execute(
                    f"""SELECT me.memory_id, me.distance
                        FROM memory_embeddings me
                        WHERE me.embedding MATCH ?
                          AND k = ?
                          AND me.partition_id IN ({placeholders})
                        ORDER BY me.distance""",
                    (vec_bytes, k, *partition_ids),
                )
            else:
                cursor = await self.db.execute(
                    """SELECT me.memory_id, me.distance
                       FROM memory_embeddings me
                       WHERE me.embedding MATCH ? AND k = ?
                       ORDER BY me.distance""",
                    (vec_bytes, k),
                )
        except aiosqlite.OperationalError:
            # Expected fallback: vec0 unavailable or the regular-table fallback
            # doesn't support MATCH. Recall degrades gracefully to other channels.
            return []
        except Exception:
            # Unexpected (e.g. a corrupted connection after a failed delete) —
            # log loudly so a silent recall collapse is observable (forgetting F9).
            logger.error("search_by_vector failed unexpectedly", exc_info=True)
            return []

        rows = list(await cursor.fetchall())
        if not rows:
            return []

        # Single round-trip fetch of full Memory rows by id, preserving
        # the vec0 ranking order.
        ids = [row["memory_id"] for row in rows[:top_k]]
        memories_by_id = await self._get_many(ids)
        results: _List[tuple[Memory, float]] = []
        for row in rows[:top_k]:
            memory = memories_by_id.get(row["memory_id"])
            if memory is None:
                continue
            # sqlite-vec returns L2 distance over unit-normalised embeddings,
            # so cosine = 1 - dist²/2. We return *true* cosine (not the old
            # 1/(1+dist) squash) because the searcher now treats this as a
            # calibrated semantic relevance: unrelated docs must score ~0, not
            # ~0.4, or they'd pollute the [0, 1] relevance scale. Ordering is
            # unchanged — the SQL already sorts by ascending distance.
            dist = float(row["distance"])
            similarity = 1.0 - (dist * dist) / 2.0
            results.append((memory, max(0.0, min(1.0, similarity))))
        return results

    async def search_by_keyword(
        self,
        query: str,
        top_k: int = 10,
        partition_ids: _List[str] | None = None,
    ) -> _List[tuple[Memory, float]]:
        """Partition-aware FTS5 BM25 search.

        ``partition_id`` is an UNINDEXED FTS5 column, so the partition
        filter sits in the same WHERE clause as MATCH and the LIMIT
        applies after the BM25 ranker has already restricted to the
        right partitions. No global LIMIT + post-filter starvation.
        """
        if not query.strip():
            return []
        match_expr = build_fts_query(query)
        if not match_expr:
            return []

        try:
            if partition_ids:
                placeholders = ",".join("?" * len(partition_ids))
                cursor = await self.db.execute(
                    f"""SELECT f.memory_id, bm25(memory_fts) AS rank
                        FROM memory_fts f
                        WHERE memory_fts MATCH ?
                          AND f.partition_id IN ({placeholders})
                        ORDER BY rank
                        LIMIT ?""",
                    (match_expr, *partition_ids, top_k * 3),
                )
            else:
                cursor = await self.db.execute(
                    """SELECT f.memory_id, bm25(memory_fts) AS rank
                       FROM memory_fts f
                       WHERE memory_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (match_expr, top_k * 3),
                )
        except aiosqlite.OperationalError:
            # Expected: a malformed MATCH expression FTS5 can't parse.
            return []
        except Exception:
            # Unexpected (e.g. a corrupted connection after a failed delete) —
            # log loudly so a silent recall collapse is observable (forgetting F9).
            logger.error("search_by_keyword failed unexpectedly", exc_info=True)
            return []

        rows = list(await cursor.fetchall())
        if not rows:
            return []
        ids = [row["memory_id"] for row in rows[:top_k]]
        memories_by_id = await self._get_many(ids)
        results: _List[tuple[Memory, float]] = []
        for row in rows[:top_k]:
            memory = memories_by_id.get(row["memory_id"])
            if memory is None:
                continue
            # FTS5 bm25() is negative-is-better, so |bm25| is a larger-is-better
            # relevance MAGNITUDE — consistent with PostgreSQL's ts_rank. We
            # return the magnitude (not the old inverted ``1/(1+|bm25|)``, where
            # the best doc got the *smallest* value); the searcher min-max
            # normalizes it for the blend re-rank, and RRF only uses order.
            results.append((memory, abs(float(row["rank"]))))
        return results

    async def corpus_size(self, partition_ids: _List[str] | None = None) -> int:
        """Number of indexed documents in scope — the ``N`` for IDF.

        Counts FTS rows (one per memory) so it matches the denominator the
        keyword IDF is computed against.
        """
        if partition_ids:
            placeholders = ",".join("?" * len(partition_ids))
            cursor = await self.db.execute(
                f"SELECT count(*) FROM memory_fts WHERE partition_id IN ({placeholders})",
                tuple(partition_ids),
            )
        else:
            cursor = await self.db.execute("SELECT count(*) FROM memory_fts")
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def keyword_doc_freqs(self, terms: _List[str], partition_ids: _List[str] | None = None) -> dict[str, int]:
        """Document frequency of each surface term via the FTS index.

        Each term is matched as a quoted single token so FTS5 applies the
        same ``porter unicode61`` tokenisation it used at index time — the DF
        therefore lines up with how the term is actually stored. Used to weight
        query terms by specificity (rare term → high IDF). Best-effort: a term
        whose MATCH errors (odd punctuation) simply gets df 0.
        """
        freqs: dict[str, int] = {}
        part_clause = ""
        part_params: tuple = ()
        if partition_ids:
            placeholders = ",".join("?" * len(partition_ids))
            part_clause = f" AND partition_id IN ({placeholders})"
            part_params = tuple(partition_ids)
        for term in terms:
            if term in freqs:
                continue
            safe = term.replace('"', "")
            if not safe:
                freqs[term] = 0
                continue
            try:
                cursor = await self.db.execute(
                    f"SELECT count(*) FROM memory_fts WHERE memory_fts MATCH ?{part_clause}",
                    (f'"{safe}"', *part_params),
                )
                row = await cursor.fetchone()
                freqs[term] = int(row[0]) if row else 0
            except Exception:
                freqs[term] = 0
        return freqs

    async def _get_many(self, memory_ids: _List[str]) -> dict[str, Memory]:
        """Batch fetch memories by id, preserving caller-side ordering.

        Returns a dict mapping memory_id → Memory so callers can index
        in whatever order the upstream ranking produced. Missing ids
        (e.g. deleted between MATCH and SELECT) are simply absent.
        """
        if not memory_ids:
            return {}
        placeholders = ",".join("?" * len(memory_ids))
        cursor = await self.db.execute(
            f"SELECT * FROM memories WHERE id IN ({placeholders})",
            tuple(memory_ids),
        )
        rows = await cursor.fetchall()
        return {row["id"]: _row_to_memory(row) for row in rows}

    async def get_by_partition(self, partition_id: str) -> _List[Memory]:
        """Fetch every memory in a partition, newest-first (no pagination, no count)."""
        cursor = await self.db.execute(
            "SELECT * FROM memories WHERE partition_id = ? ORDER BY created_at DESC",
            (partition_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_memory(r) for r in rows]

    async def get_turn_neighbors(
        self,
        partition_id: str,
        session_id: str,
        turn_min: int,
        turn_max: int,
        exclude_ids: _List[str] | None = None,
    ) -> _List[Memory]:
        """Fetch memories in *partition_id* whose metadata.session_id matches
        *session_id* and whose metadata.turn (or any value in metadata.turn_pair)
        intersects [turn_min, turn_max].

        SQLite has no JSON path index here, so this scans the partition.
        Partitions are small enough (turns of one session) that this is
        cheap, but worth replacing with a proper JSON index if we ever
        ingest tens of thousands of memories per partition.
        """
        if turn_max < turn_min:
            return []
        cursor = await self.db.execute(
            "SELECT * FROM memories WHERE partition_id = ?",
            (partition_id,),
        )
        rows = await cursor.fetchall()
        exclude = set(exclude_ids or [])

        results: _List[Memory] = []
        for row in rows:
            if row["id"] in exclude:
                continue
            try:
                meta = json.loads(row["metadata"]) if row["metadata"] else {}
            except (TypeError, ValueError):
                continue
            if str(meta.get("session_id", "")) != str(session_id):
                continue
            # A memory matches the requested turn range if its `turn`
            # falls inside it, or if any element of `turn_pair`
            # (used by the hook's per-pair summaries) falls inside it.
            turn = meta.get("turn")
            turn_pair = meta.get("turn_pair") or []
            candidates: _List[int] = []
            if isinstance(turn, int):
                candidates.append(turn)
            if isinstance(turn_pair, list):
                candidates.extend(int(t) for t in turn_pair if isinstance(t, int))
            if not candidates:
                continue
            if any(turn_min <= t <= turn_max for t in candidates):
                results.append(_row_to_memory(row))

        # Sort by turn for predictable downstream rendering.
        def _sort_key(m: Memory) -> int:
            md = m.metadata.model_dump()
            if isinstance(md.get("turn"), int):
                return int(md["turn"])
            pair = md.get("turn_pair") or []
            if isinstance(pair, list) and pair:
                return int(pair[0])
            return 0

        results.sort(key=_sort_key)
        return results

    async def delete_expired(self) -> _List[str]:
        """Delete every memory whose ``expires_at`` has passed, in one transaction.

        Returns the list of deleted memory ids (so callers can sync the
        knowledge graph / run trackers afterwards). Embedding and FTS5 rows are
        cleaned up alongside the base row.
        """
        async with self._write_lock:
            return await self._delete_expired_impl()

    async def _delete_expired_impl(self) -> _List[str]:
        """``delete_expired`` without lock acquisition — for callers already holding ``_write_lock``."""
        now = _now_iso()
        await self._begin()
        try:
            # Get expired memory IDs first (for embedding/fts cleanup)
            cursor = await self.db.execute(
                "SELECT id FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            rows = await cursor.fetchall()
            expired_ids = [row["id"] for row in rows]

            if not expired_ids:
                await self.db.commit()
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
        except BaseException:
            await self.db.rollback()
            raise
        return expired_ids

    async def update_access(self, memory_id: str) -> None:
        """Bump ``access_count`` and ``last_accessed_at`` for one memory in one transaction.

        No-op (still commits) if no row matches ``memory_id``; callers that need
        to know should ``get()`` first.
        """
        async with self._write_lock:
            await self._update_access_impl(memory_id)

    async def _update_access_impl(self, memory_id: str) -> None:
        """``update_access`` without lock acquisition — for callers already holding ``_write_lock``."""
        await self._begin()
        try:
            await self.db.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                (_now_iso(), memory_id),
            )
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise

    async def update_access_batch(self, memory_ids: _List[str]) -> None:
        """Bump access_count + last_accessed_at for several memories in one
        statement — the retrieval-strengthening write-back after a search
        touches the whole returned top-k, and per-id commits would be a
        commit storm on the interactive recall path.
        """
        if not memory_ids:
            return
        async with self._write_lock:
            await self._update_access_batch_impl(memory_ids)

    async def _update_access_batch_impl(self, memory_ids: _List[str]) -> None:
        """``update_access_batch`` without lock acquisition."""
        if not memory_ids:
            return
        placeholders = ",".join("?" * len(memory_ids))
        await self._begin()
        try:
            await self.db.execute(
                f"UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id IN ({placeholders})",
                (_now_iso(), *memory_ids),
            )
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise

    async def update_embedding(self, memory_id: str, embedding: _List[float]) -> None:
        """Overwrite a memory's embedding in one transaction.

        The embedding's length must match the declared vec0 width, otherwise an
        ``EmbeddingDimensionError`` is raised and nothing is written. An empty
        embedding is silently skipped (the storage invariant is "0-dim if unset",
        and a call with no values is treated as no-op).
        """
        if not embedding:
            return
        expected = await self._get_vec_dim()
        if expected is not None and len(embedding) != expected:
            raise EmbeddingDimensionError(f"embedding length {len(embedding)} does not match vec0 width {expected}")
        async with self._write_lock:
            await self._update_embedding_impl(memory_id, embedding, _pre_validated=True)

    async def _update_embedding_impl(
        self, memory_id: str, embedding: _List[float], *, _pre_validated: bool = False
    ) -> None:
        """``update_embedding`` without lock acquisition — for callers already holding ``_write_lock``.

        Args:
            memory_id: Memory to re-embed.
            embedding: New embedding vector.
            _pre_validated: When ``True``, dimension validation is skipped
                (caller already validated). Avoids double-checking in
                composite impl methods.
        """
        if not embedding:
            return
        if not _pre_validated:
            expected = await self._get_vec_dim()
            if expected is not None and len(embedding) != expected:
                raise EmbeddingDimensionError(f"embedding length {len(embedding)} does not match vec0 width {expected}")
        vec_bytes = np.array(embedding, dtype=np.float32).tobytes()
        await self._begin()
        try:
            # Read partition_id from the memories row so the vec0 index keeps
            # the metadata column in sync with the parent record.
            cursor = await self.db.execute("SELECT partition_id FROM memories WHERE id = ?", (memory_id,))
            row = await cursor.fetchone()
            if row is None:
                await self.db.commit()
                return
            partition_id = row["partition_id"]
            await self.db.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
            await self.db.execute(
                "INSERT INTO memory_embeddings (memory_id, partition_id, embedding) VALUES (?, ?, ?)",
                (memory_id, partition_id, vec_bytes),
            )
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise

    async def _update_content_and_embedding_impl(
        self,
        memory_id: str,
        data: MemoryUpdate,
        embedding: _List[float],
        *,
        skip_tx: bool = False,
    ) -> Memory | None:
        """Update content and re-embed in a **single transaction** (Issue #36).

        Previously ``_apply_conflict_update`` called ``update()`` then
        ``update_embedding()`` as two independent transactions — if the
        second failed, the memory's content was already changed but the
        vector still matched the old text. This method wraps both writes
        in one ``BEGIN IMMEDIATE … COMMIT`` so they either succeed as a
        unit or roll back together.

        Must be called while already holding ``_write_lock``.

        Args:
            memory_id: Memory to update.
            data: Update payload (only ``content`` is applied here).
            embedding: New embedding matching the updated content.
            skip_tx: When ``True``, skip the internal ``BEGIN IMMEDIATE … COMMIT``
                boundary. The caller manages the transaction.

        Returns:
            The updated ``Memory``, or ``None`` if the id doesn't exist.
        """
        existing = await self.get(memory_id)
        if not existing:
            return None

        # When the embedder produces an empty vector (e.g. NoopEmbedder in
        # tests), skip the embedding write — mirrors ``update_embedding``'s
        # ``if not embedding: return`` guard.
        skip_embedding = not embedding
        if not skip_embedding:
            expected = await self._get_vec_dim()
            if expected is not None and len(embedding) != expected:
                raise EmbeddingDimensionError(f"embedding length {len(embedding)} does not match vec0 width {expected}")
            vec_bytes = np.array(embedding, dtype=np.float32).tobytes()

        now = _now_iso()
        if not skip_tx:
            await self._begin()
        try:
            await self.db.execute(
                "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
                (data.content, now, memory_id),
            )
            # Sync FTS5 index to the new content.
            await self.db.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            await self.db.execute(
                "INSERT INTO memory_fts (memory_id, partition_id, content) VALUES (?, ?, ?)",
                (memory_id, existing.partition_id, data.content),
            )
            if not skip_embedding:
                # Replace the embedding vector.
                await self.db.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
                await self.db.execute(
                    "INSERT INTO memory_embeddings (memory_id, partition_id, embedding) VALUES (?, ?, ?)",
                    (memory_id, existing.partition_id, vec_bytes),
                )
            if not skip_tx:
                await self.db.commit()
        except BaseException:
            if not skip_tx:
                await self.db.rollback()
            raise
        return await self.get(memory_id)

    async def update_expiry(self, memory_id: str, expires_at: str) -> None:
        """Set ``expires_at`` (ISO timestamp) for one memory in one transaction."""
        async with self._write_lock:
            await self._update_expiry_impl(memory_id, expires_at)

    async def _update_expiry_impl(self, memory_id: str, expires_at: str) -> None:
        """``update_expiry`` without lock acquisition — for callers already holding ``_write_lock``."""
        await self._begin()
        try:
            await self.db.execute(
                "UPDATE memories SET expires_at = ? WHERE id = ?",
                (expires_at, memory_id),
            )
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise

    async def update_expiry_batch(self, items: _List[tuple[str, str]]) -> None:
        """Set ``expires_at`` for several memories under one lock + transaction.

        The forgetting sweep recomputes a TTL for every surviving memory each
        pass; per-row ``update_expiry`` commits would be a commit storm and
        leave the sweep non-atomic. This applies all updates as a single
        ``executemany`` inside one transaction (INT-6).

        Args:
            items: ``(memory_id, expires_at_iso)`` pairs. ``expires_at_iso`` is
                an ISO-8601 timestamp string (the same form ``update_expiry``
                accepts).

        Returns:
            None.
        """
        if not items:
            return
        async with self._write_lock:
            await self._update_expiry_batch_impl(items)

    async def _update_expiry_batch_impl(self, items: _List[tuple[str, str]]) -> None:
        """``update_expiry_batch`` without lock acquisition."""
        if not items:
            return
        params = [(expires_at, memory_id) for memory_id, expires_at in items]
        await self._begin()
        try:
            await self.db.executemany(
                "UPDATE memories SET expires_at = ? WHERE id = ?",
                params,
            )
            await self.db.commit()
        except BaseException:
            await self.db.rollback()
            raise
