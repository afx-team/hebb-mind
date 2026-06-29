---
description: "Get AI agent memory running in 60 seconds with no API key: install via pipx, run offline hybrid vector + keyword search, then add LLM consolidation and MCP."
---

# Quick Start

Two paths. The 60-second path needs **no API key**. The 5-minute path adds LLM-powered consolidation.

## Path A — 60 seconds, no API key

Ingest and hybrid search work fully offline using a local embedding model. The first `hebb setup` downloads a **small** embedding model — about 90MB for English (`all-MiniLM-L6-v2`) or ~470MB for multilingual (`intfloat/multilingual-e5-small`) — and only if it isn't already cached. The English/`fast` path lands in roughly a minute; multilingual takes a little longer. The high-quality bge models (1–2GB) are opt-in via `hebb setup --profile best` and are **not** downloaded by default.

### 1. Install

```bash
pipx install hebb-mind
```

Requires **Python >= 3.10**. SQLite is built in — no external database needed.

**Don't have `pipx`?** It's the standard installer for Python CLI tools — isolated venv, automatic PATH, plays nice with PEP 668. Install it once:

```bash
# macOS (Homebrew)
brew install pipx && pipx ensurepath

# Linux — Debian / Ubuntu 23.04+
sudo apt install pipx && pipx ensurepath

# Linux — Fedora
sudo dnf install pipx && pipx ensurepath

# Windows / any platform with Python 3.10+
python -m pip install --user pipx && python -m pipx ensurepath
```

Open a new terminal so the updated `PATH` takes effect, then re-run `pipx install hebb-mind`.

Prefer plain `pip`? `python -m venv .venv && source .venv/bin/activate && pip install -U hebb-mind` works fine — `hebb` lands on the venv's `PATH` automatically.

### 2. Setup

```bash
hebb setup
```

Creates `hebb.json` and `hebb.db` under the workspace, picks a **small** embedding model from your OS locale, and downloads it only if it isn't already cached. Language, region, and profile are independent flags:

```bash
hebb setup --language en --region cn      # English model, China mirror
hebb setup --language zh --region global  # Multilingual model, official HuggingFace
hebb setup --profile fast                 # smallest model (all-MiniLM, ~90MB)
hebb setup --profile best                 # high-quality bge models (1–2GB, opt-in)
```

The default `--profile default` selects `all-MiniLM-L6-v2` (~90MB) for English and `intfloat/multilingual-e5-small` (~470MB, multilingual) for Chinese/multi. Use `--profile best` for `BAAI/bge-large-en-v1.5` (English) / `BAAI/bge-m3` (multilingual) when you want the strongest retrieval and don't mind the larger download.

### 3. Install the background service

```bash
hebb service install
```

That registers Hebb Mind with launchd (macOS), systemd (Linux), or Task Scheduler (Windows) and starts it. Default scope is **per-user** — no `sudo` or admin needed. Add `--scope system` for a system-wide install.

Open <http://localhost:8321/> for the Web Console, or <http://localhost:8321/docs> for the OpenAPI page. To see where data lives, run `hebb config get workspace`.

<!-- TODO(asset): save asciinema of the 60-second path as repo_pages/public/quickstart-cast.gif, then uncomment the block below. -->
<!--
<p align="center">
  <img src="/quickstart-cast.gif" alt="Asciinema: install, setup, start, ingest, search in 60 seconds" width="720">
</p>
-->

### 4. Store and search a memory

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{
    "content": "User prefers dark mode and compact layout",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'

curl -X POST http://localhost:8321/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "UI preferences", "top_k": 5}'
```

That's it — vector + keyword + tag-graph hybrid search runs locally with no third-party calls.

## Path B — 5 minutes, with LLM consolidation

Consolidation, conflict resolution, and tag extraction need an LLM. The on/off gate is **`llm_model`** — until it is set, those endpoints run but process zero memories (a hosted provider also needs `llm_api_key`; local/proxy models do not). See [Troubleshooting](./troubleshooting.md#consolidate-returns-processed-0-or-no-conflicts-get-resolved).

### 1. Configure an LLM

```bash
hebb config set llm_model openai/gpt-4o-mini
hebb config set llm_api_key sk-your-key      # hosted providers only; skip for local/proxy models
```

Switch providers via [LiteLLM](https://github.com/BerriAI/litellm):

```bash
# Anthropic
hebb config set llm_model anthropic/claude-3-haiku-20240307

# Qwen / GLM / Kimi (OpenAI-compatible endpoint)
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
hebb config set llm_model openai/qwen-plus
```

### 2. Trigger consolidation

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

Or wait for the daily 18:00 scheduler. Tags extracted during consolidation populate the knowledge graph at `GET /api/v1/graph/tags`.

## 30-second Python SDK

The `HebbMind` facade runs the engine **in-process** — its own storage, embedder, knowledge graph, and searcher — no HTTP server required.

```python
from hebb import HebbMind

mem = HebbMind()  # resolves the workspace: $HEBB_HOME → nearest hebb.json → ~/.hebb

mem.add("User prefers dark mode", tags=["preference", "ui"], importance=7.5)

for hit in mem.search("UI preferences", top_k=5):
    print(hit.score, hit.memory.content)
```

## Service lifecycle

Hebb Mind always runs as an OS-managed background service. Manage it with:

```bash
hebb service install     # register + start (launchd / systemd / Task Scheduler)
hebb status      # show install / running state
hebb service restart     # restart in place
hebb service stop        # stop but keep installed
hebb service uninstall   # remove from the OS
```

All `service` subcommands accept `--scope user` (default, no admin) or `--scope system` (admin/sudo required, system-wide auto-start).

For Docker, see [Storage Backends](./advanced/storage-backends.md#docker-deployment).

## MCP and editor integrations

```bash
hebb claude-code install --scope user   # Claude Code: hooks-based auto memory
hebb codex install                       # Codex: project MCP + automatic memory hooks
codex mcp list                           # verify
```

For raw MCP clients (Cursor, etc.), register `hebb-mcp` by its **absolute path** (run `which hebb-mcp` to find it) — a bare `hebb-mcp` can fail to launch under GUI apps that don't inherit your shell `PATH`:

```json
{
  "mcpServers": {
    "hebb": { "command": "/absolute/path/to/hebb-mcp" }
  }
}
```

Details: [MCP Integration](./guide/mcp-integration.md) · [Claude Code Integration](./guide/claude-code.md) · [Codex Integration](./guide/codex.md)

## Next steps

- [Configuration](./guide/configuration.md) — full config reference
- [Memory Lifecycle](./concepts/memory-lifecycle.md) — how memories flow through the system
- [Benchmarks](./benchmarks/) — LoCoMo / LongMemEval results
- [API Reference](./api/memories.md) — complete API docs
