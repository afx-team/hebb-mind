"""hebb memory — bulk operations on stored memories."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from hebb.cli import reembed_checkpoint as cp_mod
from hebb.config.loader import load_settings

if TYPE_CHECKING:
    from hebb.embedding.base import EmbeddingProvider
    from hebb.storage.base import MemoryStore

console = Console()

# Flush the checkpoint to disk every N successfully processed memories. Small
# enough that an interrupt loses at most a few seconds of work; large enough
# that we don't fsync per-memory.
CHECKPOINT_FLUSH_EVERY = 32


@click.group("memory")
def memory_cmd() -> None:
    """Bulk operations on memories."""


@memory_cmd.command("reembed")
@click.option(
    "--partition",
    "partition_id",
    default=None,
    help="Re-embed only memories in this partition (default: all partitions)",
)
@click.option(
    "--batch-size",
    type=click.IntRange(1, 512),
    default=64,
    show_default=True,
    help="Memories per encode/list batch",
)
@click.option("--dry-run", is_flag=True, help="Count what would be re-embedded without writing")
@click.option(
    "--restart",
    is_flag=True,
    help="Discard any existing checkpoint and start over from the first memory",
)
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt")
def memory_reembed(
    partition_id: str | None,
    batch_size: int,
    dry_run: bool,
    restart: bool,
    yes: bool,
) -> None:
    """Recompute embeddings for stored memories using the current embedder.

    Use this after changing ``embedding_model`` or ``embedding_dim``. The
    storage schema auto-resets the vector table on dimension change at next
    service start, leaving vectors empty; this command repopulates them.

    A checkpoint file (``<workspace>/reembed.checkpoint.json``) is written
    every few dozen memories so an interrupted run can resume by simply
    invoking the command again. If the embedding model or dimension changes
    between runs, the old checkpoint is discarded automatically.
    """
    settings = load_settings()
    if not settings.embedding_enabled:
        raise click.ClickException(
            "embedding_enabled=false in config — nothing to do. "
            "Enable embeddings with: hebb config set embedding_enabled true"
        )

    if not dry_run and not yes and not sys.stdin.isatty():
        raise click.ClickException(
            "Refusing to run non-interactively without --yes. Pass --yes or run in a terminal so you can confirm."
        )

    if not dry_run and not yes:
        scope = f"partition '{partition_id}'" if partition_id else "all partitions"
        click.confirm(
            f"Re-embed every memory in {scope} using model "
            f"'{settings.embedding_model}' (dim={settings.embedding_dim})?",
            abort=True,
        )

    try:
        asyncio.run(
            _run_reembed(
                partition_id=partition_id,
                batch_size=batch_size,
                dry_run=dry_run,
                restart=restart,
            )
        )
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"reembed failed: {exc}") from exc


async def _run_reembed(*, partition_id: str | None, batch_size: int, dry_run: bool, restart: bool) -> None:
    from hebb.embedding.factory import create_embedder
    from hebb.storage.factory import create_stores

    settings = load_settings()
    workspace = settings.home_dir

    storage = await create_stores(settings)
    try:
        embedder: EmbeddingProvider = await create_embedder(settings)

        # ---------- 1. resolve checkpoint ----------
        existing = cp_mod.load(workspace)
        if (
            existing is not None
            and existing.matches(
                model=settings.embedding_model,
                dim=settings.embedding_dim,
                partition_id=partition_id,
            )
            and not restart
        ):
            cp = existing
            summary = cp_mod.summarize(cp)
            console.print(
                f"[cyan]Resuming previous reembed[/] for model "
                f"[bold]{cp.target_model}[/] (dim={cp.target_dim})"
                f"{' — partition ' + cp.partition_id if cp.partition_id else ''}: "
                f"{summary['done']}/{summary['total']} ({summary['pct']:.1f}%) already done, "
                f"{len(cp.pending_ids)} remaining."
            )
            if dry_run:
                console.print(f"[cyan]dry-run:[/] would re-embed the remaining {len(cp.pending_ids)} memories.")
                return
        else:
            if existing is not None:
                reason = (
                    "--restart specified"
                    if restart
                    else (
                        f"checkpoint target ({existing.target_model}, dim={existing.target_dim}, "
                        f"partition={existing.partition_id!r}) does not match current "
                        f"({settings.embedding_model}, dim={settings.embedding_dim}, "
                        f"partition={partition_id!r})"
                    )
                )
                console.print(f"[yellow]Discarding stale checkpoint[/] — {reason}.")
                cp_mod.delete(workspace)

            # Snapshot every memory ID we plan to process. Doing this up
            # front gives a stable work set that survives concurrent inserts.
            console.print("Scanning memories…")
            all_ids = await _collect_memory_ids(storage.memory_store, partition_id=partition_id, batch_size=batch_size)
            if not all_ids:
                scope = f"partition '{partition_id}'" if partition_id else "any partition"
                console.print(f"[yellow]No memories found in {scope}.[/]")
                return

            cp = cp_mod.ReembedCheckpoint(
                target_model=settings.embedding_model,
                target_dim=settings.embedding_dim,
                partition_id=partition_id,
                total=len(all_ids),
                pending_ids=list(all_ids),
            )

            if dry_run:
                scope = f"partition '{partition_id}'" if partition_id else "all partitions"
                console.print(
                    f"[cyan]dry-run:[/] would re-embed {cp.total} memories in {scope} "
                    f"with model '{cp.target_model}' (dim={cp.target_dim})."
                )
                return

            cp_mod.save(cp, workspace)

        # ---------- 2. process pending ----------
        completed = await _reembed_pending(
            storage.memory_store,
            embedder,
            cp,
            workspace=workspace,
            batch_size=batch_size,
        )

        # ---------- 3. cleanup ----------
        if not cp.pending_ids:
            cp_mod.delete(workspace)
            console.print(f"\n[green]Re-embed complete:[/] {completed} memories updated. Checkpoint removed.")
        else:
            cp_mod.save(cp, workspace)
            console.print(
                f"\n[yellow]Re-embed paused with {len(cp.pending_ids)} memories remaining. "
                f"Re-run `hebb memory reembed` to resume.[/]"
            )
    finally:
        await storage.close()


async def _collect_memory_ids(store: MemoryStore, *, partition_id: str | None, batch_size: int) -> list[str]:
    ids: list[str] = []
    offset = 0
    while True:
        batch, total = await store.list(partition_id=partition_id, offset=offset, limit=batch_size)
        if not batch:
            break
        ids.extend(m.id for m in batch)
        offset += len(batch)
        if offset >= total:
            break
    return ids


async def _reembed_pending(
    store: MemoryStore,
    embedder: EmbeddingProvider,
    cp: cp_mod.ReembedCheckpoint,
    *,
    workspace,
    batch_size: int,
) -> int:
    """Walk ``cp.pending_ids`` in batches, re-embedding each memory and
    removing it from ``pending_ids`` on success. The checkpoint is flushed to
    disk every CHECKPOINT_FLUSH_EVERY successful writes.

    Returns the count of memories successfully re-embedded in this invocation.
    Mutates ``cp.pending_ids`` in place.
    """
    succeeded_this_run = 0
    skipped_missing = 0
    skipped_empty = 0
    failed = 0
    since_last_flush = 0
    total = cp.total
    initial_remaining = len(cp.pending_ids)
    already_done = total - initial_remaining

    columns = (
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
    )

    try:
        with Progress(*columns, console=console, transient=False) as progress:
            task = progress.add_task("Re-embedding", total=total, completed=already_done)

            # Snapshot the work queue so we can iterate stably. We pop the
            # front of cp.pending_ids only after a memory is durably saved.
            queue = list(cp.pending_ids)
            cursor = 0
            while cursor < len(queue):
                batch_ids = queue[cursor : cursor + batch_size]
                cursor += len(batch_ids)

                # Fetch the latest content for each id (it may have changed
                # since the snapshot was taken).
                fetched: list[tuple[str, str]] = []  # (id, content)
                for mid in batch_ids:
                    mem = await store.get(mid)
                    if mem is None:
                        skipped_missing += 1
                        _drop_id(cp.pending_ids, mid)
                        progress.advance(task, 1)
                        continue
                    content = (mem.content or "").strip()
                    if not content:
                        skipped_empty += 1
                        _drop_id(cp.pending_ids, mid)
                        progress.advance(task, 1)
                        continue
                    fetched.append((mid, content))

                if not fetched:
                    continue

                ids_in_batch = [mid for mid, _ in fetched]
                texts = [text for _, text in fetched]

                try:
                    vectors = await embedder.embed_batch(texts)
                except Exception as exc:
                    failed += len(texts)
                    console.print(f"[red]batch embed failed ({len(texts)} memories): {exc}[/]")
                    progress.advance(task, len(texts))
                    continue

                for mid, vec in zip(ids_in_batch, vectors, strict=False):
                    try:
                        await store.update_embedding(mid, vec)
                    except Exception as exc:
                        failed += 1
                        console.print(f"[red]update_embedding failed for {mid}: {exc}[/]")
                        progress.advance(task, 1)
                        continue
                    _drop_id(cp.pending_ids, mid)
                    succeeded_this_run += 1
                    since_last_flush += 1
                    progress.advance(task, 1)

                if since_last_flush >= CHECKPOINT_FLUSH_EVERY:
                    cp_mod.save(cp, workspace)
                    since_last_flush = 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Persist whatever progress we have before the exception unwinds
        # past us — the outer `finally` in _run_reembed handles DB close.
        cp_mod.save(cp, workspace)
        console.print(f"\n[yellow]Interrupted. Checkpoint saved with {len(cp.pending_ids)} memories remaining.[/]")
        raise

    if skipped_missing:
        console.print(f"[yellow]Skipped (deleted): {skipped_missing}[/]")
    if skipped_empty:
        console.print(f"[yellow]Skipped (empty content): {skipped_empty}[/]")
    if failed:
        console.print(f"[red]Failed: {failed}[/]")
    console.print(f"[green]Re-embedded this run: {succeeded_this_run}[/]")
    return succeeded_this_run


def _drop_id(pending: list[str], mid: str) -> None:
    try:
        pending.remove(mid)
    except ValueError:
        pass
