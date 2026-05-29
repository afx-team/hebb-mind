#!/usr/bin/env bash
# Consolidated-mode eval on the winning retrieval config: ingest -> trigger
# memory consolidation (LLM-driven, expensive) -> re-evaluate. Full v4 pass
# (session R@k headline + end-to-end QA) so consolidated can be compared to
# the raw run on both metrics. Port 8401 (locomo dataset), own workdir
# (locomo-consolidated), robust cleanup by command pattern.
#
# Usage: run_locomo_consolidated.sh <embedding_model> <rerank:0|1>
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
EMB="${1:-BAAI/bge-large-en-v1.5}"
RR="${2:-1}"
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

rrflags=""
[ "$RR" = "1" ] && rrflags="--enable-rerank --rerank-model BAAI/bge-reranker-base"

echo ">>> CONSOLIDATED START emb=$EMB rerank=$RR  $(date +%H:%M:%S)"
cleanup_port
# --rebuild: force a clean ingest + consolidation (don't reuse a stale db).
EVAL_REPORTS_DIR=eval/reports/locomo_consolidated $PY -m eval run \
  --dataset locomo --mode consolidated --top-k 10 --rebuild \
  --embedding-model "$EMB" $rrflags
echo ">>> CONSOLIDATED DONE exit=$?  $(date +%H:%M:%S)"
cleanup_port
echo "########### CONSOLIDATED COMPLETE $(date +%H:%M:%S) ###########"
