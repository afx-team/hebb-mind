FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Pre-download embedding model (use mirror for faster download in China)
ENV HF_ENDPOINT=https://hf-mirror.com
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

VOLUME /data
ENV HIPPOCAMPUS_DB_PATH=/data/hippocampus.db
ENV HIPPOCAMPUS_KG_PATH=/data/knowledge_graph.json

EXPOSE 8321

CMD ["sh", "-c", "hippocampus init --dir /data 2>/dev/null; hippocampus start --host 0.0.0.0 --port 8321"]
