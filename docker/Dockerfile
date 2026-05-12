FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

VOLUME /data
ENV HIPPOCAMPUS_HOME=/data
ENV HIPPOCAMPUS_LANGUAGE=auto
ENV HIPPOCAMPUS_REGION=auto
ENV HIPPOCAMPUS_PROFILE=default
ENV HIPPOCAMPUS_PORT=8321

EXPOSE 8321

CMD ["sh", "-c", "hippocampus setup --language ${HIPPOCAMPUS_LANGUAGE:-auto} --region ${HIPPOCAMPUS_REGION:-auto} --profile ${HIPPOCAMPUS_PROFILE:-default}; if [ -n \"$HIPPOCAMPUS_LLM_API_KEY\" ]; then hippocampus config set llm_api_key \"$HIPPOCAMPUS_LLM_API_KEY\"; fi; if [ -n \"$HIPPOCAMPUS_LLM_MODEL\" ]; then hippocampus config set llm_model \"$HIPPOCAMPUS_LLM_MODEL\"; fi; if [ -n \"$HIPPOCAMPUS_LLM_BASE_URL\" ]; then hippocampus config set llm_base_url \"$HIPPOCAMPUS_LLM_BASE_URL\"; fi; if [ -n \"$HIPPOCAMPUS_STORAGE_TYPE\" ]; then hippocampus config set storage_type \"$HIPPOCAMPUS_STORAGE_TYPE\"; fi; if [ -n \"$HIPPOCAMPUS_PG_URL\" ]; then hippocampus config set pg_url \"$HIPPOCAMPUS_PG_URL\"; fi; hippocampus start --host 0.0.0.0 --port ${HIPPOCAMPUS_PORT:-8321}"]
