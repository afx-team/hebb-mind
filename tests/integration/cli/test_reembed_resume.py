"""End-to-end resume / discard behavior of ``hebb memory reembed``.

These tests exercise the checkpoint integration inside ``_reembed_pending``
and ``_run_reembed`` directly (not through Click) so we can simulate an
interrupt at a deterministic point.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from hebb.cli import reembed_checkpoint as cp_mod
from hebb.cli.commands import memory as mem_cmd
from hebb.models.memory import MemoryCreate


class StubEmbedder:
    """Deterministic embedder that lets a test fail mid-batch."""

    def __init__(self, dim: int = 384, fail_after: int | None = None) -> None:
        self._dim = dim
        self._fail_after = fail_after
        self.calls = 0

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed(self, text: str) -> list[float]:
        return [float(len(text)) % 1.0] * self._dim

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            self.calls += 1
            if self._fail_after is not None and self.calls > self._fail_after:
                raise RuntimeError("simulated embedder failure")
            out.append(await self.embed(t))
        return out


@pytest_asyncio.fixture
async def store(memory_store, partition_store):
    # The default partition fixture ensures `mem_hippocampus` exists.
    _ = partition_store
    for i in range(10):
        await memory_store.create(MemoryCreate(content=f"memory-{i}", partition_id="mem_hippocampus"))
    return memory_store


async def test_full_run_creates_then_deletes_checkpoint(tmp_path: Path, store) -> None:
    cp = cp_mod.ReembedCheckpoint(
        target_model="m", target_dim=384, partition_id=None, total=10, pending_ids=[]
    )
    # Collect IDs and seed checkpoint as _run_reembed would.
    ids = await mem_cmd._collect_memory_ids(store, partition_id=None, batch_size=4)
    cp.pending_ids = list(ids)
    cp.total = len(ids)
    cp_mod.save(cp, tmp_path)

    embedder = StubEmbedder()
    await mem_cmd._reembed_pending(store, embedder, cp, workspace=tmp_path, batch_size=4)

    assert cp.pending_ids == [], "all memories should have been processed"
    # Mirroring _run_reembed cleanup:
    if not cp.pending_ids:
        cp_mod.delete(tmp_path)
    assert cp_mod.load(tmp_path) is None


async def test_interrupt_then_resume_picks_up_remaining(tmp_path: Path, store) -> None:
    ids = await mem_cmd._collect_memory_ids(store, partition_id=None, batch_size=4)
    assert len(ids) == 10

    # First run: fail after 6 successful encodes.
    cp = cp_mod.ReembedCheckpoint(
        target_model="m",
        target_dim=384,
        partition_id=None,
        total=len(ids),
        pending_ids=list(ids),
    )
    cp_mod.save(cp, tmp_path)

    failing_embedder = StubEmbedder(fail_after=6)
    await mem_cmd._reembed_pending(store, failing_embedder, cp, workspace=tmp_path, batch_size=2)
    # 6 successful + 4 failed-batch memories → 6 done, 4 still pending.
    assert len(cp.pending_ids) == 4
    # Simulate _run_reembed's tail: it flushes the checkpoint when work
    # remains so subsequent invocations can resume. Batched _reembed_pending
    # doesn't flush on its own unless we cross CHECKPOINT_FLUSH_EVERY.
    cp_mod.save(cp, tmp_path)

    on_disk = cp_mod.load(tmp_path)
    assert on_disk is not None
    assert sorted(on_disk.pending_ids) == sorted(cp.pending_ids)
    assert on_disk.total == 10
    assert on_disk.target_model == "m"

    # Second run: fresh embedder, same checkpoint, processes only what's left.
    healthy_embedder = StubEmbedder()
    await mem_cmd._reembed_pending(
        store, healthy_embedder, on_disk, workspace=tmp_path, batch_size=4
    )
    assert on_disk.pending_ids == []
    assert healthy_embedder.calls == 4, "resumed run should only re-embed the remaining 4"


async def test_keyboard_interrupt_persists_checkpoint(tmp_path: Path, store) -> None:
    ids = await mem_cmd._collect_memory_ids(store, partition_id=None, batch_size=4)
    cp = cp_mod.ReembedCheckpoint(
        target_model="m", target_dim=384, partition_id=None, total=len(ids), pending_ids=list(ids)
    )

    class InterruptingEmbedder(StubEmbedder):
        async def embed_batch(self, texts: list[str]) -> list[list[float]]:
            if self.calls >= 4:
                raise KeyboardInterrupt("user hit Ctrl-C")
            return await super().embed_batch(texts)

    embedder = InterruptingEmbedder()
    with pytest.raises(KeyboardInterrupt):
        await mem_cmd._reembed_pending(store, embedder, cp, workspace=tmp_path, batch_size=2)

    # Even though we raised, the checkpoint must be on disk with the remaining ids.
    on_disk = cp_mod.load(tmp_path)
    assert on_disk is not None
    assert len(on_disk.pending_ids) == len(cp.pending_ids)


async def test_stale_checkpoint_does_not_match_when_dim_changes(tmp_path: Path) -> None:
    cp = cp_mod.ReembedCheckpoint(
        target_model="old", target_dim=384, partition_id=None, total=5, pending_ids=["a", "b"]
    )
    cp_mod.save(cp, tmp_path)

    loaded = cp_mod.load(tmp_path)
    assert loaded is not None
    # Same model name, different dim → not a match
    assert not loaded.matches(model="old", dim=1024, partition_id=None)
    # Same dim, different model → not a match
    assert not loaded.matches(model="new", dim=384, partition_id=None)
    # Same model + dim but different partition scope → not a match
    assert not loaded.matches(model="old", dim=384, partition_id="mem_user")
    # All three equal → match
    assert loaded.matches(model="old", dim=384, partition_id=None)
