# Claude Code Integration

Hebb Mind integrates with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) as both an **MCP server** (manual memory tools) and a **hooks-based auto-memory layer** (automatic write/recall across sessions).

## Overview

| Mode | What it does | How it works |
|------|-------------|--------------|
| **MCP Server** | Manual `write_memory`, `search_memory`, `consolidate` tools | Claude calls tools on demand |
| **Hooks (auto-memory)** | Automatically writes each user message and recalls cross-session context | Claude Code hooks fire on session lifecycle events |

Most users want both — MCP for explicit memory operations, hooks for seamless background memory.

## Install

```bash
pip install -U hebb-mind       # Install the package
hebb setup                     # Initialize + prefetch embedding model
hebb claude-code install --scope user   # Inject hooks + MCP into Claude Code
```

That's it. Restart Claude Code and Hebb Mind will:

- **Recall** cross-session memories at the start of each session
- **Write** each user message to memory (with noise stripping and dedup)
- **Consolidate** memories when the session ends

### Scope

By default, `hebb claude-code install` writes hooks to the **project-level** `.claude/settings.json`. To install globally:

```bash
hebb claude-code install --scope user   # writes to ~/.claude/settings.json
```

### Uninstall

```bash
hebb claude-code uninstall              # remove hooks + MCP from settings
```

## How Hooks Work

Claude Code [hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) are shell commands that fire on session lifecycle events. Hebb Mind registers three:

```
SessionStart ──→ hebb claude-code recall ──→ search API ──→ stdout (injected into context)
UserPromptSubmit ──→ hebb claude-code write ──→ strip noise + dedup ──→ write API (silent)
Stop ──→ hebb claude-code stop ──→ consolidate API + cleanup (silent)
```

### Recall (SessionStart)

When a new Claude Code session starts, `hebb claude-code recall` searches for relevant memories and outputs them to stdout. Claude Code injects this output into the conversation context.

- Searches with `top_k=20`, returns up to 10 results
- **Filters out current session memories** — they're already in context
- Output format:

```xml
<cross-session-memory source="hebb" count="3">
[mem_preference] (score=0.85 tags=[food, preference]) User likes salmon
[mem_semantic] (score=0.72 tags=[coding]) User prefers TypeScript over JavaScript
[mem_episodic] (score=0.68) Debugged auth middleware last session
</cross-session-memory>
```

### Write (UserPromptSubmit)

Each time the user sends a message, `hebb claude-code write` captures it:

1. **Strips noise** — removes `<system-reminder>`, `<command-name>`, and other system tags
2. **Skips trivial messages** — anything under 20 characters ("ok", "yes", "/clear")
3. **Deduplicates** — SHA-256 hash check prevents writing the same content twice per session
4. **Writes silently** — no stdout output, so the user sees no interruption

Memories are written to the `mem_hippocampus` working inbox with `source: "hook"` and the session ID in metadata.

### Stop

When the session ends, `hebb claude-code stop`:

1. Triggers memory consolidation (classifies working inbox memories into long-term partitions)
2. Cleans up the per-session dedup state

## MCP Server

The MCP server provides explicit memory tools that Claude can call during conversation:

| Tool | Description | Parameters |
|------|-------------|------------|
| `write_memory` | Write a memory to the working-memory inbox | `content`, `tags?`, `importance?` |
| `search_memory` | Hybrid retrieval (vector + keyword + graph) | `query`, `top_k?` |
| `consolidate` | Trigger memory consolidation | none |

### Manual MCP Setup

If you only want the MCP server without hooks, add to `.mcp.json`:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "hebb-mcp"
    }
  }
}
```

Or use Claude Code's MCP command:

```bash
claude mcp add --transport stdio --scope user hebb -- hebb-mcp
claude mcp list
```

See [MCP Integration](./mcp-integration.md) for details on Claude Desktop, Cursor, and remote service configuration.

## Configuration

The hooks use the same `hebb.json` config as the main service. No additional configuration is needed.

If the hebb service isn't running when a hook fires, the hook asks the OS service manager (launchd / systemd / Task Scheduler) to start it. If the service is not yet installed, run `hebb service install` once.

For remote services, set the `HEBB_URL` environment variable:

```bash
export HEBB_URL=http://192.168.1.100:8321
```

## Troubleshooting

### Hooks not firing

Verify hooks are registered:

```bash
cat .claude/settings.json | grep "hebb claude-code"
```

If empty, re-run `hebb claude-code install`.

### No memories recalled

Check that the service is running and has memories:

```bash
hebb status
curl http://localhost:8321/api/v1/memories?limit=5
```

### Recall is slow

The first recall after a cold start loads the embedding model. `hebb setup` prefetches the default model to make this path predictable. Keep the service running with `hebb service install` (the OS service manager will restart it after crashes and reboots).
