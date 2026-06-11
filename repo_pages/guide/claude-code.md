---
description: "Give Claude Code long-term memory: install the Hebb Mind MCP server plus session hooks for automatic cross-session recall, turn capture, and consolidation."
---

# Claude Code Integration

Hebb Mind integrates with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) as both an **MCP server** (manual memory tools) and a **hooks-based auto-memory layer** (automatic recall and turn capture across sessions).

## Overview

| Mode | What it does | How it works |
|------|-------------|--------------|
| **MCP Server** | Manual `write_memory`, `search_memory`, `consolidate`, `ingest_conversation` tools | Claude calls tools on demand |
| **Hooks (auto-memory)** | Recalls cross-session context and captures each user/assistant turn | Claude Code hooks fire on session lifecycle events |

Most users want both — MCP for explicit memory operations, hooks for seamless background memory.

## Install

The supported way to wire Hebb Mind into Claude Code is the `hebb claude-code install` command. It resolves the absolute path to `hebb` / `hebb-mcp` and writes both the hooks and the MCP server entry into Claude Code's settings:

```bash
pipx install hebb-mind                   # Install the CLI (use `pipx upgrade hebb-mind` to update)
hebb setup                               # Initialize + download the embedding model
hebb claude-code install --scope user    # Inject hooks + MCP into Claude Code
```

No `pipx`? See [Installation → Install pipx](./installation.md#install-pipx-if-you-don-t-have-it).

That's it. Restart Claude Code and Hebb Mind will:

- **Recall** cross-session memories at the start of each session and before each prompt
- **Capture** each completed user/assistant turn to the working-memory inbox

Consolidation (merging duplicates, resolving conflicts, extracting tags) does **not** run at the end of a session — it runs on the `consolidation_time` schedule, or on demand via `POST /api/v1/admin/consolidate`.

### Scope

`--scope user` (recommended) writes to `~/.claude/settings.json` and applies to every project. `--scope project` writes to the current directory's `.claude/settings.json` and scopes the integration to that project only. Pick one consistently:

```bash
hebb claude-code install --scope user      # global, all projects (recommended)
hebb claude-code install --scope project   # this project only
```

### Uninstall

```bash
hebb claude-code uninstall --scope user    # remove hooks + MCP from ~/.claude/settings.json
hebb claude-code uninstall --scope project # remove from this project's .claude/settings.json
```

## How Hooks Work

Claude Code [hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) are shell commands that fire on session lifecycle events. Hebb Mind registers three (the installer injects each as an **absolute** path, not a bare `hebb`):

```
SessionStart     ──→ hebb claude-code recall ──→ search API ──→ stdout (injected into context)
UserPromptSubmit ──→ hebb claude-code prompt ──→ prompt-relevant search ──→ stdout (injected)
Stop             ──→ hebb claude-code stop   ──→ capture last turn ──→ write API (silent)
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

### Prompt (UserPromptSubmit)

Each time the user submits a prompt, `hebb claude-code prompt` **recalls** memories relevant to *that prompt* and injects them into context. This hook does **not** write memory — it is the per-turn recall path that complements the broader SessionStart recall.

### Stop (turn capture)

When a turn completes, `hebb claude-code stop` captures it:

1. Reads the **last user + assistant turn** from the session transcript
2. **Strips noise** — system reminders, command tags, and subagent (Task-tool) sidechain lines
3. **Deduplicates** per `session_id` + turn index so a re-fired Stop doesn't write twice
4. **Writes silently** to the `mem_hippocampus` working inbox with `source: "hook:stop"`

This is where user turns are written to memory. Note that a *re-fired* Stop event for the same final turn is deduped, so you won't see duplicate entries. Consolidation of these inbox memories happens later, on the schedule (see above) — not at Stop.

## MCP Server

The MCP server provides explicit memory tools that Claude can call during conversation:

| Tool | Description | Parameters |
|------|-------------|------------|
| `write_memory` | Write a memory to the working-memory inbox | `content`, `tags?`, `importance?` |
| `search_memory` | Hybrid retrieval (vector + keyword + graph) | `query`, `top_k?` |
| `consolidate` | Trigger memory consolidation | none |
| `ingest_conversation` | Ingest a conversation export (Claude Code JSONL / ChatGPT JSON / plain text) | `content`, `format_hint?`, `importance?` |

### Manual MCP Setup

`hebb claude-code install` already registers the MCP server. If you only want the MCP server **without** the hooks, register `hebb-mcp` by its **absolute path** — a bare `hebb-mcp` can fail to launch under GUI-launched Claude Code that doesn't inherit your shell `PATH`. Find the path with `which hebb-mcp`, then add it to `.mcp.json`:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

Or use Claude Code's MCP command (pass the absolute path after `--`):

```bash
claude mcp add --transport stdio --scope user hebb -- "$(which hebb-mcp)"
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
