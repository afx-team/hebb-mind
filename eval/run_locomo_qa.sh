#!/usr/bin/env bash
# End-to-end QA eval (LLM-as-judge) on the winning retrieval config.
# Uses the dedicated locomo-qa benchmark (port 8407, isolated from the
# matrix's 8401 and the 8321 daily service). Concurrency + key rotation
# come from eval.json (concurrency=4, 5 keys). Robust server cleanup by
# command pattern so no orphan carries over.
#
# Usage: run_locomo_qa.sh <embedding_model> <rerank:0|1>
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
EMB="${1:-BAAI/bge-large-en-v1.5}"
RR="${2:-1}"
PORT=8407
PAT="uvicorn hebb.server.app:app --host 0.0.0.0 --port $PORT"

cleanup_port() {
  pkill -9 -f "$PAT" 2>/dev/null
  for _ in $(seq 1 20); do
    lsof -ti :$PORT >/dev/null 2>&1 || return 0
    sleep 1
  done
  echo "WARN: port $PORT still busy"
}

rrflags=""
[ "$RR" = "1" ] && rrflags="--enable-rerank --rerank-model BAAI/bge-reranker-base"

echo ">>> QA START emb=$EMB rerank=$RR  $(date +%H:%M:%S)"
cleanup_port
EVAL_REPORTS_DIR=eval/reports/locomo_qa $PY -m eval run \
  --dataset locomo-qa --mode raw --top-k 10 \
  --embedding-model "$EMB" $rrflags
echo ">>> QA DONE exit=$?  $(date +%H:%M:%S)"
cleanup_port
echo "########### QA COMPLETE $(date +%H:%M:%S) ###########"
