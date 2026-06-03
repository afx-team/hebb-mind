#!/usr/bin/env bash
# MemBench full-category sweep — one isolated db PER category group so each
# vec0 table stays small (≤~145k vectors), keeping partition-scoped search
# in the fast ~2.6s/query regime. A single combined 1.12M-vector db makes
# sqlite-vec brute-force the KNN per query (10-20s) — see run notes.
#
# Each invocation writes its own eval/reports/membench/v1/run-N. Per-category
# numbers come from each report's accuracy_by_category + per_category_hit_at_k
# (keyed by real category name), so aggregation is order-independent.
set -u
cd "$(dirname "$0")/.."

PY=.venv/bin/python
COMMON=(--dataset membench --mode raw --top-k 5
        --embedding-model all-MiniLM-L6-v2
        --enable-rerank --rerank-model BAAI/bge-reranker-base)

# 7 big roles/events categories run solo (~140k mem each); 4 small
# movie/food/book + RecMultiSession grouped (~117k mem total).
CAT_GROUPS=(
  "noisy"
  "aggregative"
  "comparative"
  "conditional"
  "knowledge_update"
  "post_processing"
  "simple"
  "highlevel,highlevel_rec,lowlevel_rec"
)
# NOTE: RecMultiSession already covered by its own run (validation run-6).

echo "SWEEP_START $(date +%H:%M:%S)  groups=${#CAT_GROUPS[@]}"
for cats in "${CAT_GROUPS[@]}"; do
  echo "=================================================="
  echo "CATEGORY_GROUP_START $cats  $(date +%H:%M:%S)"
  echo "=================================================="
  MEMBENCH_CATEGORIES="$cats" MEMBENCH_TOPIC="" "$PY" -m eval run "${COMMON[@]}"
  echo "CATEGORY_GROUP_DONE $cats  exit=$?  $(date +%H:%M:%S)"
done
echo "SWEEP_ALL_DONE $(date +%H:%M:%S)"
