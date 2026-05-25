"""Partition CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from hebb.models.partition import Partition, PartitionCreate, PartitionUpdate
from hebb.server.dependencies import get_partition_store
from hebb.storage.base import PartitionStore

router = APIRouter()


@router.get("/partitions", response_model=list[Partition])
async def list_partitions(
    store: PartitionStore = Depends(get_partition_store),
):
    return await store.list()


@router.get("/partitions/{partition_id}", response_model=Partition)
async def get_partition(
    partition_id: str,
    store: PartitionStore = Depends(get_partition_store),
):
    partition = await store.get(partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="Partition not found")
    return partition


@router.post("/partitions", response_model=Partition, status_code=201)
async def create_partition(
    data: PartitionCreate,
    store: PartitionStore = Depends(get_partition_store),
):
    existing = await store.get(data.id)
    if existing:
        raise HTTPException(status_code=409, detail="Partition already exists")
    return await store.create(data)


@router.patch("/partitions/{partition_id}", response_model=Partition)
async def update_partition(
    partition_id: str,
    data: PartitionUpdate,
    store: PartitionStore = Depends(get_partition_store),
):
    partition = await store.update(partition_id, data)
    if not partition:
        raise HTTPException(status_code=404, detail="Partition not found")
    return partition


@router.delete("/partitions/{partition_id}", status_code=204)
async def delete_partition(
    partition_id: str,
    store: PartitionStore = Depends(get_partition_store),
):
    existing = await store.get(partition_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Partition not found")
    if existing.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system partition")
    await store.delete(partition_id)
