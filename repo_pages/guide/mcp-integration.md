---
description: "Connect Claude Code, Codex, Cursor, and Claude Desktop to long-term AI agent memory over MCP — write, recall via hybrid vector+keyword search, and consolidate."
---

# MCP Integration

Hebb Mind provides an MCP (Model Context Protocol) server that exposes memory operations as tools. Claude Code, Codex, Cursor, and other MCP-compatible clients can use it directly.

## Prerequisites

Hebb Mind runs as an OS-managed background service (launchd / systemd / Task Scheduler). The MCP server discovers the service URL and asks the service manager to start it if it isn't running:

```bash
hebb setup              # first time only — picks model and HuggingFace mirror
hebb service install    # registers the background service (no admin by default)
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `write_memory` | Write a memory to the working-memory inbox | `content`, `tags?`, `importance?` |
| `search_memory` | Hybrid retrieval (vector + keyword + graph) | `query`, `top_k?` |
| `consolidate` | Trigger memory consolidation | none |
| `ingest_conversation` | Ingest a conversation export (Claude Code JSONL / ChatGPT JSON / plain text) — auto-detects format, normalizes turns, stores each turn | `content`, `format_hint?`, `importance?` |

## Configuration

The MCP server automatically discovers the service address from `hebb.json`. For the common case (service running locally), no configuration is needed — just add the command.

::: tip Use the absolute path to `hebb-mcp`
The snippets below show `command: "hebb-mcp"` for brevity, but a **bare** `hebb-mcp` can fail to launch under GUI-launched apps (Claude Desktop, Cursor) that don't inherit your shell `PATH` — the MCP server then silently never starts. Run `which hebb-mcp` (Windows: `where hebb-mcp`) and use the **absolute path** as the `command`. The `hebb claude-code install` / `hebb codex install` commands already do this for you.
:::

If the service runs on a remote host or non-default address, set `HEBB_URL`:

### Claude Code

Recommended:

```bash
hebb claude-code install --scope user
```

MCP-only:

Add to your project's `.mcp.json` (replace `/absolute/path/to/hebb-mcp` with the output of `which hebb-mcp`):

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

Or add globally in `~/.claude.json`.

If the service runs on a non-default address, set the URL explicitly:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp",
      "env": {
        "HEBB_URL": "http://192.168.1.100:8321"
      }
    }
  }
}
```

### Codex

Recommended:

```bash
hebb codex install   # Codex registers MCP servers globally (global-only)
codex mcp list
```

Native Codex command (pass the absolute path so it resolves regardless of how Codex is launched):

```bash
codex mcp add hebb -- "$(which hebb-mcp)"
```

### Claude Desktop

Add to `claude_desktop_config.json` (typically at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS). Claude Desktop is a GUI app, so the **absolute path** to `hebb-mcp` (from `which hebb-mcp`) is required:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

### Cursor

Open **Settings → Features → MCP** and add (Cursor is a GUI app — use the absolute path from `which hebb-mcp`):

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

## How It Works

```
Claude Code / Codex / Cursor
        │ (stdio)
        v
  hebb-mcp (MCP server)
        │ (HTTP)
        v
  hebb _serve (REST API on port 8321, run by the OS service manager)
        │
  Storage / Embedder / Searcher
```

The MCP server is a thin wrapper that translates MCP tool calls into HTTP requests to the running Hebb Mind service. All storage, embedding, and search logic stays in the main server.

## CLI Usage

You can also start the MCP server directly:

```bash
hebb mcp serve
```

This runs in stdio mode, suitable for direct integration with MCP clients.

## Example Workflow

Once configured, an AI agent can:

1. **Store context**: "Remember that the user prefers TypeScript over JavaScript"
2. **Recall later**: "What are the user's language preferences?"
3. **Organize**: Trigger consolidation to classify memories into partitions

The agent uses these tools naturally during conversation without explicit API calls.
