#!/usr/bin/env bash
# Re-run the MemBench categories that failed in the conc-8 sweep
# (conditional crashed; the grouped movie-cats run hung — suspected
# OOM on a 16GB box under 8 concurrent rerank calls). Each category
# runs SOLO at concurrency 4 (eval.json) — run-5's proven-stable
# setting. Hit@k is concurrency-independent, so these numbers are
# directly comparable to the conc-8 runs.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
COMMON=(--dataset membench --mode raw --top-k 5
        --embedding-model all-MiniLM-L6-v2
        --enable-rerank --rerank-model BAAI/bge-reranker-base)

CAT_LIST=("conditional" "highlevel" "highlevel_rec" "lowlevel_rec")

echo "RERUN_START $(date +%H:%M:%S)  n=${#CAT_LIST[@]}"
for cats in "${CAT_LIST[@]}"; do
  echo "=================================================="
  echo "RERUN_CAT_START $cats  $(date +%H:%M:%S)"
  echo "=================================================="
  MEMBENCH_CATEGORIES="$cats" MEMBENCH_TOPIC="" "$PY" -m eval run "${COMMON[@]}"
  echo "RERUN_CAT_DONE $cats  exit=$?  $(date +%H:%M:%S)"
done
echo "RERUN_ALL_DONE $(date +%H:%M:%S)"
