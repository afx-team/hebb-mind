"""Hebb Mind Python SDK — five-minute tour.

This script walks through the core SDK surface:

    1. Add memories to different partitions (semantic / episodic / preference).
    2. Search and print top results with relevance scores.
    3. List memories filtered by partition.
    4. Delete a memory and confirm it's gone.
    5. Run consolidation and report how many items were processed.

Run it
------

    # Default workspace at examples/data/ (DB lands at examples/data/hebb.db)
    python examples/01_python_sdk_basics.py

    # Wipe the example workspace before running (re-runnable)
    python examples/01_python_sdk_basics.py --reset

    # Or point at any workspace directory you like
    python examples/01_python_sdk_basics.py --home /tmp/hebb-demo --reset

The facade resolves its workspace from ``$HEBB_HOME`` (a directory); the DB
always lives at ``<workspace>/hebb.db``. The script never makes a network call
on import — everything happens inside ``main()``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from hebb import HebbMind

DEFAULT_HOME = Path("examples/data")

SEED_MEMORIES: list[tuple[str, str, list[str]]] = [
    # (content, partition, tags)
    ("Python's GIL serializes bytecode execution within a single process.", "mem_semantic", ["python"]),
    ("RAG = Retrieval-Augmented Generation; retrieve docs then condition the LLM.", "mem_semantic", ["rag"]),
    ("On 2026-04-19 I shipped the launch prep PR.", "mem_episodic", ["release"]),
    ("I prefer dark mode and 2-space indentation in my editor.", "mem_preference", ["ui"]),
    ("To restart the local server: `hebb service restart`.", "mem_procedural", ["cli"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", type=Path,
                        default=Path(os.environ.get("HEBB_HOME", DEFAULT_HOME)),
                        help="Workspace directory (default: examples/data). "
                             "The DB lives at <home>/hebb.db.")
    parser.add_argument("--reset", action="store_true",
                        help="Delete the example DB before running so the demo starts clean.")
    return parser.parse_args()


def reset_db(home: Path) -> None:
    """Wipe the example workspace DB so re-runs start from a clean slate."""
    home.mkdir(parents=True, exist_ok=True)
    db_path = home / "hebb.db"
    if db_path.exists():
        db_path.unlink()
        print(f"[reset] removed {db_path}")


def main() -> None:
    args = parse_args()
    args.home.mkdir(parents=True, exist_ok=True)
    if args.reset:
        reset_db(args.home)

    # The facade resolves its workspace (and therefore the DB path) from HEBB_HOME.
    os.environ.setdefault("HEBB_HOME", str(args.home.resolve()))
    hc = HebbMind()

    # 1. Seed five memories across four partitions ---------------------------
    print("\n[1/5] Adding 5 memories...")
    ids: list[str] = []
    for content, partition, tags in SEED_MEMORIES:
        mem = hc.add(content, partition=partition, tags=tags)
        ids.append(mem.id)
        print(f"    + [{partition}] id={mem.id[:8]}  {content[:60]}...")

    # 2. Search ---------------------------------------------------------------
    query = "How does Python handle multiple threads?"
    print(f"\n[2/5] Searching: {query!r}")
    results = hc.search(query, top_k=3)
    for rank, hit in enumerate(results, start=1):
        score = getattr(hit, "score", None)
        mem = getattr(hit, "memory", hit)
        print(f"    {rank}. score={score:.3f}  {mem.content[:80]}")

    # 3. List by partition ----------------------------------------------------
    # hc.list() returns a (memories, total) tuple — unpack it.
    print("\n[3/5] Listing mem_preference partition:")
    prefs, _total = hc.list(partition="mem_preference")
    for mem in prefs:
        print(f"    - {mem.content}")

    # 4. Delete one and confirm ----------------------------------------------
    target = ids[0]
    print(f"\n[4/5] Deleting id={target[:8]}...")
    hc.delete(target)
    all_mems, _ = hc.list()
    remaining = {m.id for m in all_mems}
    assert target not in remaining, "Delete did not take effect"
    print(f"    confirmed gone (now have {len(remaining)} memories)")

    # 5. Consolidate ----------------------------------------------------------
    print("\n[5/5] Running consolidation...")
    report = hc.consolidate()
    processed = getattr(report, "processed", report)
    print(f"    consolidation processed {processed} memories")

    print("\nDone. Re-run with --reset to start over.")


if __name__ == "__main__":
    main()
