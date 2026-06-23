"""Per-partition forgetting configuration + non-destructive preview.

Forgetting parameters are operator *policy*, not data, so per-partition overrides
live in hebb.json (``Settings.forgetting_overrides``) rather than the partitions
table. These endpoints read/write that config map and expose a read-only preview
that runs the real forgetting math over a partition's live memories without
deleting anything — the data feed for the console's tuning UI (curve + matrix +
impact count).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from hebb.config.loader import update_forgetting_overrides
from hebb.config.settings import (
    FORGETTING_COEFF_MAX,
    FORGETTING_HALF_LIFE_MAX_DAYS,
    PartitionForgettingOverride,
    Settings,
)
from hebb.constants import PartitionType
from hebb.scheduler.forgetting_job import (
    compute_expires_at,
    resolve_forgetting_params,
    resolve_inherited_params,
)
from hebb.server.dependencies import get_memory_store, get_partition_store, get_settings
from hebb.server.forgetting_tracker import list_runs as list_forget_runs
from hebb.storage.base import MemoryStore, PartitionStore

router = APIRouter()

_PREVIEW_SAMPLE_LIMIT = 20


class ForgettingParamsInput(BaseModel):
    """Candidate forgetting parameters (for a PUT override or a preview).

    A ``None`` numeric field inherits the partition's region/global default;
    ``enabled=False`` exempts the partition from forgetting.
    """

    half_life_days: float | None = Field(default=None, gt=0, le=FORGETTING_HALF_LIFE_MAX_DAYS)
    k_importance: float | None = Field(default=None, ge=0, le=FORGETTING_COEFF_MAX)
    k_access: float | None = Field(default=None, ge=0, le=FORGETTING_COEFF_MAX)
    threshold: float | None = Field(default=None, gt=0, lt=1)
    enabled: bool = Field(default=True)


class EffectiveForgetting(BaseModel):
    """Resolved retention-model parameters a partition is swept with."""

    half_life_days: float
    k_importance: float
    k_access: float
    threshold: float
    enabled: bool


class PartitionForgettingEntry(BaseModel):
    """One partition's forgetting config: override + resolved effect + inherit baseline."""

    id: str
    name: str
    is_system: bool
    swept: bool
    memory_count: int
    override: ForgettingParamsInput | None
    effective: EffectiveForgetting
    # Region/global baseline IGNORING the override — what each field falls back to
    # when its override is cleared, so the tuner can show the inherited value.
    inherited: EffectiveForgetting


class ForgettingConfigResponse(BaseModel):
    """Global forgetting defaults + per-partition entries for the tuning UI."""

    global_half_life_days: float
    global_k_importance: float
    global_k_access: float
    global_threshold: float
    min_retention_days: float
    forget_interval_seconds: int
    partitions: list[PartitionForgettingEntry]


class ForgettingPreviewSample(BaseModel):
    """One memory's projected fate under the candidate parameters."""

    id: str
    content: str
    importance_score: float
    access_count: int
    days_since_access: float
    projected_expires_at: datetime | None
    would_forget: bool


class ForgettingPreviewResponse(BaseModel):
    """Result of running the forgetting math over a partition without deleting."""

    partition_id: str
    swept: bool
    half_life_days: float
    k_importance: float
    k_access: float
    threshold: float
    total: int
    would_forget: int
    would_keep: int
    sample: list[ForgettingPreviewSample]


class ForgettingRunEntry(BaseModel):
    """One forgetting sweep's record (from the in-process run tracker)."""

    run_id: str
    trigger: str
    status: str
    started_at: float
    finished_at: float | None
    scanned: int
    deleted: int
    partitions_swept: int
    error: str | None


class ForgettingRunsResponse(BaseModel):
    """Recent forgetting sweep history for the console's records view."""

    runs: list[ForgettingRunEntry]


def _entry(
    partition_id: str,
    name: str,
    is_system: bool,
    memory_count: int,
    settings: Settings,
) -> PartitionForgettingEntry:
    """Build the config view for one partition from the live settings."""
    swept = partition_id != PartitionType.HIPPOCAMPUS.value
    override = settings.forgetting_overrides.get(partition_id)
    resolved = resolve_forgetting_params(partition_id, settings)
    inherited = resolve_inherited_params(partition_id, settings)
    return PartitionForgettingEntry(
        id=partition_id,
        name=name,
        is_system=is_system,
        swept=swept,
        memory_count=memory_count,
        override=(ForgettingParamsInput(**override.model_dump()) if override is not None else None),
        effective=EffectiveForgetting(
            half_life_days=resolved.half_life_days,
            k_importance=resolved.k_importance,
            k_access=resolved.k_access,
            threshold=resolved.threshold,
            # HIPPOCAMPUS is never swept regardless of any override.
            enabled=resolved.enabled and swept,
        ),
        inherited=EffectiveForgetting(
            half_life_days=inherited.half_life_days,
            k_importance=inherited.k_importance,
            k_access=inherited.k_access,
            threshold=inherited.threshold,
            enabled=True,
        ),
    )


def _persist_and_sync(settings: Settings, new_map: dict[str, dict[str, object]]) -> None:
    """Validate + write the overrides map to hebb.json, then sync live settings."""
    try:
        _, validated = update_forgetting_overrides(new_map)
    except FileNotFoundError as exc:  # pragma: no cover - daemon always has hebb.json
        raise HTTPException(
            status_code=500,
            detail="No hebb.json found to persist forgetting overrides",
        ) from exc
    settings.forgetting_overrides = {pid: PartitionForgettingOverride(**fields) for pid, fields in validated.items()}


@router.get("/forgetting", response_model=ForgettingConfigResponse)
async def get_forgetting_config(
    store: PartitionStore = Depends(get_partition_store),
    settings: Settings = Depends(get_settings),
) -> ForgettingConfigResponse:
    """Return global forgetting defaults and each partition's override + effect."""
    partitions = await store.list()
    return ForgettingConfigResponse(
        global_half_life_days=settings.half_life_days,
        global_k_importance=settings.k_importance,
        global_k_access=settings.k_access,
        global_threshold=settings.forget_threshold,
        min_retention_days=settings.forget_min_retention_days,
        forget_interval_seconds=settings.forget_interval_seconds,
        partitions=[_entry(p.id, p.name, p.is_system, p.memory_count, settings) for p in partitions],
    )


@router.get("/forgetting/runs", response_model=ForgettingRunsResponse)
async def list_forgetting_runs() -> ForgettingRunsResponse:
    """Return recent forgetting sweep records (most-recent first)."""
    return ForgettingRunsResponse(runs=[ForgettingRunEntry(**r.to_dict()) for r in list_forget_runs()])


@router.put("/forgetting/{partition_id}", response_model=PartitionForgettingEntry)
async def set_forgetting_override(
    partition_id: str,
    params: ForgettingParamsInput,
    store: PartitionStore = Depends(get_partition_store),
    settings: Settings = Depends(get_settings),
) -> PartitionForgettingEntry:
    """Set (or replace) a partition's forgetting override and persist it.

    Takes effect on the next forgetting sweep — the scheduler reads the live
    settings each tick, so no restart is required.
    """
    partition = await store.get(partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="Partition not found")

    override = PartitionForgettingOverride(
        half_life_days=params.half_life_days,
        k_importance=params.k_importance,
        k_access=params.k_access,
        threshold=params.threshold,
        enabled=params.enabled,
    )
    new_map = {pid: o.model_dump() for pid, o in settings.forgetting_overrides.items()}
    new_map[partition_id] = override.model_dump()
    _persist_and_sync(settings, new_map)

    return _entry(partition.id, partition.name, partition.is_system, partition.memory_count, settings)


@router.delete("/forgetting/{partition_id}", response_model=PartitionForgettingEntry)
async def clear_forgetting_override(
    partition_id: str,
    store: PartitionStore = Depends(get_partition_store),
    settings: Settings = Depends(get_settings),
) -> PartitionForgettingEntry:
    """Clear a partition's override so it inherits the global defaults again."""
    partition = await store.get(partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="Partition not found")

    new_map = {pid: o.model_dump() for pid, o in settings.forgetting_overrides.items() if pid != partition_id}
    _persist_and_sync(settings, new_map)

    return _entry(partition.id, partition.name, partition.is_system, partition.memory_count, settings)


@router.post("/forgetting/{partition_id}/preview", response_model=ForgettingPreviewResponse)
async def preview_forgetting(
    partition_id: str,
    params: ForgettingParamsInput,
    store: PartitionStore = Depends(get_partition_store),
    memory_store: MemoryStore = Depends(get_memory_store),
    settings: Settings = Depends(get_settings),
) -> ForgettingPreviewResponse:
    """Project how many memories the next sweep would forget under *params*.

    Read-only — runs the exact production ``compute_expires_at`` over the
    partition's current memories so the count matches what the real sweep would
    do, but deletes nothing.
    """
    partition = await store.get(partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="Partition not found")

    # Null candidate fields inherit the partition's region/global baseline.
    inherited = resolve_inherited_params(partition_id, settings)
    half_life = params.half_life_days if params.half_life_days is not None else inherited.half_life_days
    k_importance = params.k_importance if params.k_importance is not None else inherited.k_importance
    k_access = params.k_access if params.k_access is not None else inherited.k_access
    threshold = params.threshold if params.threshold is not None else inherited.threshold
    # HIPPOCAMPUS is never swept; a disabled override forgets nothing.
    swept = params.enabled and partition_id != PartitionType.HIPPOCAMPUS.value

    now = datetime.now(timezone.utc)
    memories = await memory_store.get_by_partition(partition_id)
    would_forget = 0
    sample: list[ForgettingPreviewSample] = []
    for memory in memories:
        if swept:
            expires_at = compute_expires_at(
                memory,
                half_life_days=half_life,
                k_importance=k_importance,
                k_access=k_access,
                threshold=threshold,
                min_retention_days=settings.forget_min_retention_days,
            )
            forget = expires_at < now
        else:
            expires_at = None
            forget = False
        if forget:
            would_forget += 1
        if len(sample) < _PREVIEW_SAMPLE_LIMIT:
            days_since = (now - memory.last_accessed_at).total_seconds() / 86400.0
            sample.append(
                ForgettingPreviewSample(
                    id=memory.id,
                    content=memory.content[:160],
                    importance_score=memory.importance_score,
                    access_count=memory.access_count,
                    days_since_access=round(days_since, 2),
                    projected_expires_at=expires_at,
                    would_forget=forget,
                )
            )

    total = len(memories)
    return ForgettingPreviewResponse(
        partition_id=partition_id,
        swept=swept,
        half_life_days=half_life,
        k_importance=k_importance,
        k_access=k_access,
        threshold=threshold,
        total=total,
        would_forget=would_forget,
        would_keep=total - would_forget,
        sample=sample,
    )
