#!/usr/bin/env bash
# Retrieval matrix v3 — fast embedders only. bge-m3 dropped: it hangs
# during ingest on this offline CPU box (XLM-RoBERTa-large fp32, no GPU;
# db growth stalled, >17 min no progress). bge-large already has valid
# results and is not re-run. Robust per-config isolation (kill by command
# pattern on --port 8401, never the 8321 daily service).
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
MATRIX_ROOT=eval/reports/locomo/matrix
RERANKER="BAAI/bge-reranker-base"
PORT=8401
PAT="uvicorn hebb.server.app:app --host 0.0.0.0 --port $PORT"

cleanup_port() {
  pkill -9 -f "$PAT" 2>/dev/null
  for _ in $(seq 1 20); do
    lsof -ti :$PORT >/dev/null 2>&1 || return 0
    sleep 1
  done
  echo "WARN: port $PORT still busy"
}

CONFIGS=(
  "minilm__norerank|all-MiniLM-L6-v2|0"
  "minilm__rerank|all-MiniLM-L6-v2|1"
  "e5small__norerank|intfloat/multilingual-e5-small|0"
  "e5small__rerank|intfloat/multilingual-e5-small|1"
  "jinav3__norerank|jinaai/jina-embeddings-v3|0"
)

for entry in "${CONFIGS[@]}"; do
  IFS='|' read -r name emb rr <<< "$entry"
  echo "==================================================================="
  echo ">>> MATRIX3 CONFIG: $name  (embedding=$emb rerank=$rr)  $(date +%H:%M:%S)"
  echo "==================================================================="
  rm -rf "${MATRIX_ROOT:?}/$name"
  cleanup_port
  rrflags=""
  [ "$rr" = "1" ] && rrflags="--enable-rerank --rerank-model $RERANKER"
  EVAL_REPORTS_DIR="$MATRIX_ROOT/$name" $PY -m eval run \
    --dataset locomo --mode raw --skip-qa --top-k 10 \
    --embedding-model "$emb" $rrflags
  echo ">>> DONE3 CONFIG: $name  exit=$?  $(date +%H:%M:%S)"
  cleanup_port
done
echo "########### MATRIX3 COMPLETE $(date +%H:%M:%S) ###########"
