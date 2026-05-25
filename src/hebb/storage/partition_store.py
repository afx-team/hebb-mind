"""SQLite implementation of PartitionStore."""

from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

from hebb.constants import (
    DEFAULT_PARTITION_DESCRIPTIONS,
    DEFAULT_PARTITION_NAMES,
    SYSTEM_PARTITIONS,
)
from hebb.models.partition import Partition, PartitionCreate, PartitionUpdate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_partition(row: aiosqlite.Row) -> Partition:
    return Partition(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        enabled=bool(row["enabled"]),
        is_system=bool(row["is_system"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class SQLitePartitionStore:
    """SQLite-backed partition store."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(self, data: PartitionCreate, is_system: bool = False) -> Partition:
        now = _now_iso()
        await self.db.execute(
            """INSERT INTO partitions (id, name, description, enabled, is_system, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data.id, data.name, data.description, int(data.enabled), int(is_system), now, now),
        )
        await self.db.commit()
        return await self.get(data.id)  # type: ignore[return-value]

    async def get(self, partition_id: str) -> Partition | None:
        cursor = await self.db.execute(
            "SELECT * FROM partitions WHERE id = ?",
            (partition_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        partition = _row_to_partition(row)

        # Get memory count
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM memories WHERE partition_id = ?",
            (partition_id,),
        )
        count_row = await cursor.fetchone()
        partition.memory_count = count_row[0] if count_row else 0

        return partition

    async def list(self) -> list[Partition]:
        cursor = await self.db.execute(
            "SELECT * FROM partitions ORDER BY (id = 'mem_hippocampus') DESC, created_at",
        )
        rows = await cursor.fetchall()
        partitions = []
        for row in rows:
            p = _row_to_partition(row)
            # Get memory count
            c = await self.db.execute(
                "SELECT COUNT(*) FROM memories WHERE partition_id = ?",
                (p.id,),
            )
            count_row = await c.fetchone()
            p.memory_count = count_row[0] if count_row else 0
            partitions.append(p)
        return partitions

    async def update(self, partition_id: str, data: PartitionUpdate) -> Partition | None:
        existing = await self.get(partition_id)
        if not existing:
            return None

        updates = []
        params: list = []
        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if data.description is not None:
            updates.append("description = ?")
            params.append(data.description)
        if data.enabled is not None:
            updates.append("enabled = ?")
            params.append(int(data.enabled))

        if not updates:
            return existing

        updates.append("updated_at = ?")
        params.append(_now_iso())
        params.append(partition_id)

        await self.db.execute(
            f"UPDATE partitions SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.commit()
        return await self.get(partition_id)

    async def delete(self, partition_id: str) -> bool:
        # Cannot delete system partitions
        existing = await self.get(partition_id)
        if not existing or existing.is_system:
            return False

        await self.db.execute(
            "DELETE FROM partitions WHERE id = ?",
            (partition_id,),
        )
        await self.db.commit()
        return True

    async def ensure_defaults(self) -> None:
        """Create all default system partitions if they don't exist."""
        for pt in SYSTEM_PARTITIONS:
            existing = await self.get(pt.value)
            if not existing:
                await self.create(
                    data=PartitionCreate(
                        id=pt.value,
                        name=DEFAULT_PARTITION_NAMES[pt],
                        description=DEFAULT_PARTITION_DESCRIPTIONS[pt],
                        enabled=True,
                    ),
                    is_system=True,
                )
