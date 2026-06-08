# MCP Quickstart — give your AI coding agent persistent memory

Hebb Mind ships an [MCP](https://modelcontextprotocol.io/) server. One CLI
command wires it into Claude Code or Codex, and the agent immediately gains a
small set of "remember this" / "what do you know about X" tools.

## Install (pick your client)

First make sure the background service is installed and running — the MCP tools
talk to the local REST server on port 8321, and `hebb ... install` configures
the client but does **not** install the service for you:

```bash
hebb setup              # one-time: download the local embedding model (small)
hebb service install    # one-time: register + start the background service
```

Then wire up your client:

```bash
# Claude Code (writes to ~/.claude/settings.json with --scope user)
hebb claude-code install --scope user

# Codex CLI (writes to ~/.codex/config.toml with --scope user)
hebb codex install --scope user
```

Restart the client. That's it.

To uninstall:

```bash
hebb claude-code uninstall
hebb codex uninstall --scope user
```

## What tools does the MCP server expose?

The server (`src/hebb/mcp/server.py`) registers four tools that the
agent can call autonomously:

| Tool | What it does |
|------|--------------|
| `write_memory(content, tags?, importance?)` | Store a new memory in the working inbox. The consolidation agent later sorts it into a long-term partition (semantic / episodic / preference / procedural). |
| `search_memory(query, top_k=5)` | Hybrid retrieval — vector similarity + keyword match + knowledge-graph expansion — over all stored memories. |
| `consolidate()` | Manually trigger the consolidation pass that organizes new memories and extracts tags into the knowledge graph. |
| `ingest_conversation(content, format_hint?, importance?)` | Bulk-import a Claude Code JSONL or ChatGPT JSON export so previous chats become memories. |

If the background service is installed (see above) but stopped, the MCP server
will start it on first use. If no service is installed, the MCP tools fail to
reach the REST server — run `hebb service install` first.

## Try it — three prompts

Once installed, your agent can do things like:

> **You:** Remember that I prefer pytest over unittest, and I always use
> ruff + mypy strict in new Python projects.
>
> **Agent:** *(calls `write_memory`)* Got it.

> **You:** What do you remember about the `hebb-mind` project?
>
> **Agent:** *(calls `search_memory("hebb-mind project")`)* You're working
> on an open-source agent memory framework with a SQLite + sqlite-vec
> backend, a FastAPI server on port 8321, and Claude Code / Codex MCP
> integrations.

> **You:** Pull in my `~/exports/chatgpt-2026-04.json` and consolidate.
>
> **Agent:** *(calls `ingest_conversation` then `consolidate`)* Imported 312
> memories; consolidation processed 312 / succeeded 308 / failed 4.

## Going deeper

- Full MCP integration guide (with troubleshooting and config schema):
  [docs site → guide → MCP integration](../repo_pages/guide/mcp-integration.md)
- Claude Code-specific hooks (recall cross-session memories on session start,
  recall prompt-relevant memories on user message, capture the last turn on
  stop — consolidation runs on a schedule, not on stop):
  [`repo_pages/guide/claude-code.md`](../repo_pages/guide/claude-code.md)
- Codex setup details:
  [`repo_pages/guide/codex.md`](../repo_pages/guide/codex.md)
