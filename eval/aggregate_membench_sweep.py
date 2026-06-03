"""Aggregate a MemBench per-category sweep into one table vs MemPalace.

Reads every report under eval/reports/membench/v1/run-N whose run number
is >= --min-run, pulls config.per_category_hit_at_k (keyed by the real
category name, so run order doesn't matter), de-duplicates by category
(latest run wins), and prints a per-category Hit@k table next to
MemPalace's published Recall@5 (movie topic, top-5).

Usage:
    .venv/bin/python eval/aggregate_membench_sweep.py --min-run 6
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# MemPalace published Recall@5 (movie topic, hybrid, top-5) — from
# docs/analysis/mempalace-benchmark-deep-dive.md §"MemBench (ACL 2025…)".
# RecMultiSession is absent from their per-category table.
MEMPALACE_HIT5: dict[str, float] = {
    "aggregative": 0.993,
    "comparative": 0.984,
    "knowledge_update": 0.960,
    "simple": 0.959,
    "highlevel": 0.958,
    "lowlevel_rec": 0.998,
    "highlevel_rec": 0.762,
    "post_processing": 0.566,
    "conditional": 0.573,
    "noisy": 0.434,
}
MEMPALACE_OVERALL = 0.803


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="eval/reports/membench/v1")
    ap.add_argument("--min-run", type=int, default=6)
    args = ap.parse_args()

    version_dir = Path(args.reports)
    # category -> (run_n, {hit@k: float, n: float})
    by_cat: dict[str, tuple[int, dict[str, float]]] = {}
    for run_dir in sorted(version_dir.glob("run-*")):
        try:
            n = int(run_dir.name.split("-")[1])
        except (IndexError, ValueError):
            continue
        if n < args.min_run:
            continue
        jpath = run_dir / "membench.json"
        if not jpath.exists():
            continue
        data = json.loads(jpath.read_text())
        per_cat = data.get("config", {}).get("per_category_hit_at_k", {})
        for cat, metrics in per_cat.items():
            if cat not in by_cat or n > by_cat[cat][0]:
                by_cat[cat] = (n, metrics)

    if not by_cat:
        print("No per_category_hit_at_k found in runs >=", args.min_run)
        return

    # Overall = n-weighted mean of per-category hit@5.
    tot_n = sum(m["n"] for _, m in by_cat.values())
    overall = {
        k: sum(m[k] * m["n"] for _, m in by_cat.values()) / tot_n
        for k in ("hit@1", "hit@3", "hit@5", "hit@10")
    }

    print(f"\nMemBench per-category sweep — all topics, top_k=5, "
          f"all-MiniLM + bge-reranker-base (rerank ON)")
    print(f"{int(tot_n)} memories' worth of questions across "
          f"{len(by_cat)} categories\n")
    hdr = f"| {'Category':<18} | {'n':>5} | {'Hit@1':>6} | {'Hit@3':>6} | {'Hit@5':>6} | {'Hit@10':>6} | {'MemPalace@5':>11} | {'Δ@5':>7} |"
    print(hdr)
    print("|" + "-" * 20 + "|" + "-" * 7 + "|" + "-" * 8 + "|" + "-" * 8
          + "|" + "-" * 8 + "|" + "-" * 8 + "|" + "-" * 13 + "|" + "-" * 9 + "|")
    for cat in sorted(by_cat, key=lambda c: by_cat[c][1]["hit@5"]):
        n_run, m = by_cat[cat]
        mp = MEMPALACE_HIT5.get(cat)
        mp_s = f"{mp*100:.1f}%" if mp is not None else "—"
        delta = f"{(m['hit@5']-mp)*100:+.1f}pp" if mp is not None else "—"
        print(f"| {cat:<18} | {int(m['n']):>5} | {m['hit@1']*100:>5.1f}% "
              f"| {m['hit@3']*100:>5.1f}% | {m['hit@5']*100:>5.1f}% "
              f"| {m['hit@10']*100:>5.1f}% | {mp_s:>11} | {delta:>7} |")
    print(f"| {'OVERALL (wtd)':<18} | {int(tot_n):>5} | {overall['hit@1']*100:>5.1f}% "
          f"| {overall['hit@3']*100:>5.1f}% | {overall['hit@5']*100:>5.1f}% "
          f"| {overall['hit@10']*100:>5.1f}% | {MEMPALACE_OVERALL*100:>10.1f}% "
          f"| {(overall['hit@5']-MEMPALACE_OVERALL)*100:>+6.1f}pp |")
    print("\n(per-category run mapping:)")
    for cat in sorted(by_cat):
        print(f"  {cat:<18} run-{by_cat[cat][0]}")


if __name__ == "__main__":
    main()
