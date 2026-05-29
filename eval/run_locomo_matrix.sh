#!/usr/bin/env bash
# Retrieval-only (skip-qa) LoCoMo matrix: embedding model x rerank.
# Full 10 scenarios. Each config gets its own isolated workdir/db (raw
# mode always wipes + re-ingests, so each embedding is re-encoded clean)
# and its own reports dir. Resilient: a failing config (e.g. a model that
# needs trust_remote_code offline) is logged and skipped, the rest run on.
set -u
cd "$(dirname "$0")/.."   # project root
PY=.venv/bin/python
MATRIX_ROOT=eval/reports/locomo/matrix
RERANKER="BAAI/bge-reranker-base"

# config_name | embedding_model | rerank(0/1)
CONFIGS=(
  "bge-large__norerank|BAAI/bge-large-en-v1.5|0"
  "bge-large__rerank|BAAI/bge-large-en-v1.5|1"
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
  echo ">>> MATRIX CONFIG: $name  (embedding=$emb rerank=$rr)  $(date +%H:%M:%S)"
  echo "==================================================================="
  rrflags=""
  if [ "$rr" = "1" ]; then
    rrflags="--enable-rerank --rerank-model $RERANKER"
  fi
  EVAL_REPORTS_DIR="$MATRIX_ROOT/$name" $PY -m eval run \
    --dataset locomo --mode raw --skip-qa --top-k 10 \
    --embedding-model "$emb" $rrflags
  echo ">>> DONE CONFIG: $name  exit=$?  $(date +%H:%M:%S)"
done
echo "########### MATRIX COMPLETE $(date +%H:%M:%S) ###########"
