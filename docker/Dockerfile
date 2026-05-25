FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

VOLUME /data
ENV HEBB_HOME=/data
ENV HEBB_LANGUAGE=auto
ENV HEBB_REGION=auto
ENV HEBB_PROFILE=default
ENV HEBB_PORT=8321

EXPOSE 8321

CMD ["sh", "-c", "hebb setup --language ${HEBB_LANGUAGE:-auto} --region ${HEBB_REGION:-auto} --profile ${HEBB_PROFILE:-default}; if [ -n \"$HEBB_LLM_API_KEY\" ]; then hebb config set llm_api_key \"$HEBB_LLM_API_KEY\"; fi; if [ -n \"$HEBB_LLM_MODEL\" ]; then hebb config set llm_model \"$HEBB_LLM_MODEL\"; fi; if [ -n \"$HEBB_LLM_BASE_URL\" ]; then hebb config set llm_base_url \"$HEBB_LLM_BASE_URL\"; fi; if [ -n \"$HEBB_STORAGE_TYPE\" ]; then hebb config set storage_type \"$HEBB_STORAGE_TYPE\"; fi; if [ -n \"$HEBB_PG_URL\" ]; then hebb config set pg_url \"$HEBB_PG_URL\"; fi; hebb start --host 0.0.0.0 --port ${HEBB_PORT:-8321}"]
