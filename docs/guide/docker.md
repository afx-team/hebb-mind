# Docker Deployment

Hippocampus provides a Dockerfile and Docker Compose configuration for containerized deployment.

## Quick Start with Docker Compose

```bash
git clone https://github.com/afx-team/hippocampus.git
cd hippocampus
docker compose -f docker/docker-compose.yml up
```

The server will be available at [http://localhost:8321/](http://localhost:8321/).

## Build and Run Manually

```bash
# Build the image
docker build -f docker/Dockerfile -t hippocampus .

# Run the container
docker run -p 8321:8321 -v hippocampus-data:/data hippocampus
```

The container stores data in `/data` (SQLite database and knowledge graph). Mount a volume to persist data across container restarts.

## Environment Variables

When running in Docker, configuration can be passed via environment variables. These override the values in `hippocampus.json`:

| Variable | Description | Default |
|----------|-------------|---------|
| `HIPPOCAMPUS_LLM_API_KEY` | LLM provider API key | -- |
| `HIPPOCAMPUS_LLM_MODEL` | LLM model identifier | `openai/gpt-4o-mini` |
| `HIPPOCAMPUS_LLM_BASE_URL` | Custom LLM API endpoint | -- |
| `HIPPOCAMPUS_DB_PATH` | Database file path | `/data/hippocampus.db` |
| `HIPPOCAMPUS_KG_PATH` | Knowledge graph file path | `/data/knowledge_graph.json` |
| `HIPPOCAMPUS_GITHUB_CLIENT_ID` | GitHub OAuth client ID | -- |
| `HIPPOCAMPUS_GITHUB_CLIENT_SECRET` | GitHub OAuth client secret | -- |
| `HIPPOCAMPUS_JWT_SECRET` | JWT signing secret | `change-me-in-production` |

## Docker Compose with Environment Variables

Create a `.env` file alongside `docker-compose.yml`:

```bash
HIPPOCAMPUS_LLM_API_KEY=sk-your-key-here
HIPPOCAMPUS_LLM_MODEL=openai/gpt-4o-mini
```

Then run:

```bash
docker compose -f docker/docker-compose.yml up -d
```

## Docker Compose Configuration

The provided `docker-compose.yml` configuration:

```yaml
services:
  hippocampus:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8321:8321"
    volumes:
      - hippocampus-/data
    environment:
      - HIPPOCAMPUS_LLM_API_KEY=${HIPPOCAMPUS_LLM_API_KEY}
      - HIPPOCAMPUS_LLM_MODEL=${HIPPOCAMPUS_LLM_MODEL:-openai/gpt-4o-mini}
      - HIPPOCAMPUS_LLM_BASE_URL=${HIPPOCAMPUS_LLM_BASE_URL:-}
    restart: unless-stopped

volumes:
  hippocampus-
```

## What the Container Does

1. Installs Hippocampus and all dependencies
2. Pre-downloads the embedding model (`all-MiniLM-L6-v2`)
3. On startup, runs `hippocampus init` to ensure the database exists
4. Starts the server on `0.0.0.0:8321`

## Production Considerations

- Always set `HIPPOCAMPUS_JWT_SECRET` to a strong random value in production
- Mount a persistent volume for `/data` to avoid data loss
- For PostgreSQL backends, configure `pg_url` via environment variable or config file
- Consider placing a reverse proxy (nginx, Caddy) in front for TLS termination
