"""Collect LoCoMo retrieval-matrix results into a ranked comparison table.

Reads ``eval/reports/locomo/matrix/<config>/locomo/v4/run-*/locomo.json``
and prints accuracy (session-level R@10 hit rate) + mean Recall@k per
config, then a comparison against the published MemPalace baselines.
"""

from __future__ import annotations

import json
from pathlib import Path

MATRIX_ROOT = Path(__file__).resolve().parent / "reports" / "locomo" / "matrix"

# Published MemPalace session-level R@10 baselines (top_k=10, full 1,986q).
# Computed from .research/mempalace/benchmarks/*.json (raw + hybrid) and the
# documented bge-large hybrid figure in repo_pages/benchmarks/locomo/vs-mempalace.md.
MEMPALACE = {
    "raw (MiniLM)": {"hit": 0.6493, "recall": 0.6021, "emb": "MiniLM-384"},
    "hybrid (MiniLM)": {"hit": 0.9263, "recall": 0.8889, "emb": "MiniLM-384"},
    "bge-large hybrid": {"hit": 0.924, "recall": None, "emb": "bge-large-1024"},
}


def _latest_run(config_dir: Path) -> Path | None:
    cands = sorted(config_dir.glob("locomo/*/run-*/locomo.json"))
    return cands[-1] if cands else None


def main() -> None:
    rows = []
    if not MATRIX_ROOT.is_dir():
        print(f"No matrix dir at {MATRIX_ROOT}")
        return
    for config_dir in sorted(MATRIX_ROOT.iterdir()):
        if not config_dir.is_dir():
            continue
        jp = _latest_run(config_dir)
        if jp is None:
            rows.append((config_dir.name, None, None, None, None, "NO RESULT"))
            continue
        d = json.loads(jp.read_text())
        rm = d.get("retrieval_metrics", {})
        rows.append((
            config_dir.name,
            d.get("accuracy"),
            rm.get("avg_recall_at_k"),
            d.get("total_questions"),
            rm.get("avg_retrieval_latency_ms"),
            "ok",
        ))

    # Sort by accuracy (hit@k) desc, None last.
    rows.sort(key=lambda r: (r[1] is None, -(r[1] or 0)))

    print("\n=== LoCoMo retrieval matrix (session R@10, full 10 scenarios) ===\n")
    print(f"{'config':<24} {'hit@10':>8} {'mean R@k':>9} {'q':>6} {'lat(ms)':>9}  status")
    print("-" * 72)
    for name, acc, recall, q, lat, status in rows:
        acc_s = f"{acc*100:.2f}" if acc is not None else "—"
        rec_s = f"{recall:.4f}" if recall is not None else "—"
        q_s = str(q) if q is not None else "—"
        lat_s = f"{lat:.0f}" if lat is not None else "—"
        print(f"{name:<24} {acc_s:>8} {rec_s:>9} {q_s:>6} {lat_s:>9}  {status}")

    print("\n=== MemPalace published baselines (R@10, full 1,986q) ===\n")
    print(f"{'system':<24} {'hit@10':>8} {'mean R@k':>9}  embedding")
    print("-" * 60)
    for name, m in MEMPALACE.items():
        hit_s = f"{m['hit']*100:.2f}" if m["hit"] is not None else "—"
        rec_s = f"{m['recall']:.4f}" if m["recall"] is not None else "—"
        print(f"{name:<24} {hit_s:>8} {rec_s:>9}  {m['emb']}")

    # Best config
    ok_rows = [r for r in rows if r[1] is not None]
    if ok_rows:
        best = ok_rows[0]
        print(f"\n>>> BEST: {best[0]}  hit@10={best[1]*100:.2f}%  meanR@k={best[2]:.4f}")


if __name__ == "__main__":
    main()
