# Getting Started

Get Hippocampus up and running in under two minutes.

## Prerequisites

- Python >= 3.12
- An LLM API key (OpenAI, Anthropic, Qwen, etc.)

## Installation

```bash
pip install afx-hippocampus
```

Or use the one-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh
```

## Initialize a Project

```bash
hippocampus init
```

This creates two files in your current directory:

- `hippocampus.json` -- configuration file
- `hippocampus.db` -- SQLite database (default storage backend)

## Configure Your LLM

Memory consolidation requires an LLM. Set your API key:

```bash
hippocampus config set llm_api_key sk-your-key-here
```

Optionally change the model (default is `openai/gpt-4o-mini`):

```bash
hippocampus config set llm_model openai/gpt-4o
```

For Chinese model providers (Qwen, GLM, Kimi), also set the base URL:

```bash
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
hippocampus config set llm_model openai/qwen-plus
```

## Start the Server

```bash
hippocampus start
```

The server starts on port 8321 by default.

- **Web Console**: [http://localhost:8321/](http://localhost:8321/) -- visual interface for managing memories, searching, and exploring the knowledge graph
- **API Documentation**: [http://localhost:8321/docs](http://localhost:8321/docs) -- interactive Swagger/OpenAPI docs

## Store Your First Memory

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers dark mode and compact layout",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

## Search Memories

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI preferences", "top_k": 5}'
```

## Trigger Consolidation

The consolidation agent runs automatically on a schedule (default: every hour). To trigger it manually:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

## Next Steps

- [Configuration](./configuration.md) -- customize all settings
- [Memory Lifecycle](../concepts/memory-lifecycle.md) -- understand how memories flow through the system
- [API Reference](../api/memories.md) -- full API documentation
- [Docker Deployment](./docker.md) -- run with Docker
