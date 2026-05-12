# Quick Start

Get Hippocampus up and running in under a minute.

## 1. Install

```bash
pip install -U afx-hippocampus
```

Requires **Python >= 3.10**. No external database needed — SQLite is built in.

## 2. Setup

```bash
hippocampus setup
```

This creates `hippocampus.json` and `hippocampus.db`, detects your content language, selects an embedding model, detects the best download source, and prefetches the model.

Language and region are independent:

```bash
hippocampus setup --language en --region cn      # English model, China mirror
hippocampus setup --language zh --region global  # Multilingual model, official HuggingFace
```

## 3. Start

```bash
hippocampus start
```

Open [http://localhost:8321/](http://localhost:8321/) for the Web Console, or [http://localhost:8321/docs](http://localhost:8321/docs) for the API docs.

To see where your data is stored, run:

```bash
hippocampus workspace
```

## Keep It Running

`hippocampus start` runs in the foreground. To run in the background:

```bash
hippocampus start -d
```

To auto-start on boot:

```bash
hippocampus service install
```

This generates the appropriate config (systemd on Linux, launchd on macOS) and enables the service. To remove:

```bash
hippocampus service uninstall
```

For Docker deployment, see [Storage Backends](./advanced/storage-backends.md#docker-deployment).

## Store & Search

Write a memory:

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers dark mode and compact layout",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

Search memories:

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI preferences", "top_k": 5}'
```

## Enable Consolidation

Memory consolidation (auto-classifying memories into partitions) requires an LLM:

```bash
hippocampus config set llm_api_key sk-your-key-here
```

Switch models via [LiteLLM](https://github.com/BerriAI/litellm):

```bash
hippocampus config set llm_model openai/gpt-4o          # OpenAI
hippocampus config set llm_model anthropic/claude-3-haiku-20240307  # Anthropic
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1  # Qwen/GLM/Kimi
hippocampus config set llm_model openai/qwen-plus
```

Trigger consolidation manually:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

## MCP Integration

Use Hippocampus as an MCP tool in Claude Code, Cursor, or other MCP clients:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp"
    }
  }
}
```

See [MCP Integration](./guide/mcp-integration.md) for full setup instructions.

## Claude Code Auto-Memory

Give Claude Code persistent memory across sessions with hooks:

```bash
hippocampus cc install --scope user
```

This registers three hooks in `.claude/settings.json`:

- **SessionStart** — recalls cross-session memories into context
- **UserPromptSubmit** — writes each user message to memory (with noise stripping and dedup)
- **Stop** — triggers consolidation when the session ends

See [Claude Code Integration](./guide/claude-code.md) for details.

## Codex MCP Tools

Add Hippocampus memory tools to Codex:

```bash
hippocampus codex install --scope user
codex mcp list
```

See [Codex Integration](./guide/codex.md) for details.

## Next Steps

- [Installation](./guide/installation.md) — optional extras, from-source install
- [Configuration](./guide/configuration.md) — full config reference
- [Memory Lifecycle](./concepts/memory-lifecycle.md) — how memories flow through the system
- [API Reference](./api/memories.md) — complete API documentation
