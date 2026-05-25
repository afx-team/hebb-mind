"""Hebb Mind Python SDK — five-minute tour.

This script walks through the core SDK surface:

    1. Add memories to different partitions (semantic / episodic / preference).
    2. Search and print top results with relevance scores.
    3. List memories filtered by partition.
    4. Delete a memory and confirm it's gone.
    5. Run consolidation and report how many items were processed.

Run it
------

    # Default DB at examples/data/example.db
    python examples/01_python_sdk_basics.py

    # Wipe the example DB before running (re-runnable)
    python examples/01_python_sdk_basics.py --reset

    # Or point at any path you like
    python examples/01_python_sdk_basics.py --db-path /tmp/hippo.db --reset

The script never makes a network call on import — everything happens inside
``main()``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from hebb import HebbMind

DEFAULT_DB_PATH = Path("examples/data/example.db")

SEED_MEMORIES: list[tuple[str, str, list[str]]] = [
    # (content, partition, tags)
    ("Python's GIL serializes bytecode execution within a single process.", "mem_semantic", ["python"]),
    ("RAG = Retrieval-Augmented Generation; retrieve docs then condition the LLM.", "mem_semantic", ["rag"]),
    ("On 2026-04-19 I shipped the v0.1.1 launch prep PR.", "mem_episodic", ["release"]),
    ("I prefer dark mode and 2-space indentation in my editor.", "mem_preference", ["ui"]),
    ("To restart the local server: `hebb stop && hebb start`.", "mem_procedural", ["cli"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-path", type=Path,
                        default=Path(os.environ.get("HEBB_DB_PATH", DEFAULT_DB_PATH)),
                        help="SQLite database path (default: examples/data/example.db).")
    parser.add_argument("--reset", action="store_true",
                        help="Delete the DB file before running so the demo starts clean.")
    return parser.parse_args()


def reset_db(db_path: Path) -> None:
    """Wipe the example DB so re-runs start from a clean slate."""
    if db_path.exists():
        db_path.unlink()
        print(f"[reset] removed {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    if args.reset:
        reset_db(args.db_path)
    args.db_path.parent.mkdir(parents=True, exist_ok=True)

    # The facade picks up HEBB_DB_PATH from env if not passed explicitly.
    os.environ.setdefault("HEBB_DB_PATH", str(args.db_path))
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
    print("\n[3/5] Listing mem_preference partition:")
    for mem in hc.list(partition="mem_preference"):
        print(f"    - {mem.content}")

    # 4. Delete one and confirm ----------------------------------------------
    target = ids[0]
    print(f"\n[4/5] Deleting id={target[:8]}...")
    hc.delete(target)
    remaining = {m.id for m in hc.list()}
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
