#!/usr/bin/env bash
# Retrieval matrix v2 — re-run the configs contaminated by orphan-server
# carryover. Robust per-config isolation: kill the eval server BY COMMAND
# PATTERN (matches only "...--port 8401", never the 8321 daily service,
# never client connections) and wait for the port to free, before AND
# after each config. This sidesteps the eval CLI's lsof-based stop_server
# (which matches client sockets and times out under load, leaving orphans).
# bge-large already has valid results and is NOT re-run here.
set -u
cd "$(dirname "$0")/.."   # project root
PY=.venv/bin/python
MATRIX_ROOT=eval/reports/locomo/matrix
RERANKER="BAAI/bge-reranker-base"
PORT=8401
PAT="uvicorn hebb.server.app:app --host 0.0.0.0 --port $PORT"

cleanup_port() {
  pkill -9 -f "$PAT" 2>/dev/null
  for _ in $(seq 1 20); do
    lsof -ti :$PORT >/dev/null 2>&1 || { return 0; }
    sleep 1
  done
  echo "WARN: port $PORT still busy after cleanup"
}

CONFIGS=(
  "bge-m3__norerank|BAAI/bge-m3|0"
  "bge-m3__rerank|BAAI/bge-m3|1"
  "minilm__norerank|all-MiniLM-L6-v2|0"
  "minilm__rerank|all-MiniLM-L6-v2|1"
  "e5small__norerank|intfloat/multilingual-e5-small|0"
  "e5small__rerank|intfloat/multilingual-e5-small|1"
  "jinav3__norerank|jinaai/jina-embeddings-v3|0"
)

for entry in "${CONFIGS[@]}"; do
  IFS='|' read -r name emb rr <<< "$entry"
  echo "==================================================================="
  echo ">>> MATRIX2 CONFIG: $name  (embedding=$emb rerank=$rr)  $(date +%H:%M:%S)"
  echo "==================================================================="
  rm -rf "${MATRIX_ROOT:?}/$name"   # drop any partial report from the bad run
  cleanup_port
  rrflags=""
  if [ "$rr" = "1" ]; then
    rrflags="--enable-rerank --rerank-model $RERANKER"
  fi
  EVAL_REPORTS_DIR="$MATRIX_ROOT/$name" $PY -m eval run \
    --dataset locomo --mode raw --skip-qa --top-k 10 \
    --embedding-model "$emb" $rrflags
  echo ">>> DONE2 CONFIG: $name  exit=$?  $(date +%H:%M:%S)"
  cleanup_port
done
echo "########### MATRIX2 COMPLETE $(date +%H:%M:%S) ###########"
