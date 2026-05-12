# MCP Integration

Hippocampus provides an MCP (Model Context Protocol) server that exposes memory operations as tools. Claude Code, Codex, Cursor, and other MCP-compatible clients can use it directly.

## Prerequisites

The hippocampus service must be running. The MCP server will auto-start it if not detected:

```bash
hippocampus setup    # first time only
hippocampus start    # or: hippocampus start -d (daemon mode)
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `write_memory` | Write a memory to the hippocampus inbox | `content`, `tags?`, `importance?` |
| `search_memory` | Hybrid retrieval (vector + keyword + graph) | `query`, `top_k?` |
| `consolidate` | Trigger memory consolidation | none |

## Configuration

The MCP server automatically discovers the service address from `hippocampus.json`. For the common case (service running locally), no configuration is needed — just add the command.

If the service runs on a remote host or non-default address, set `HIPPOCAMPUS_URL`:

### Claude Code

Recommended:

```bash
hippocampus cc install --scope user
```

MCP-only:

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp"
    }
  }
}
```

Or add globally in `~/.claude.json`.

If the service runs on a non-default address, set the URL explicitly:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp",
      "env": {
        "HIPPOCAMPUS_URL": "http://192.168.1.100:8321"
      }
    }
  }
}
```

### Codex

Recommended:

```bash
hippocampus codex install --scope user
codex mcp list
```

Native Codex command:

```bash
codex mcp add hippocampus -- hippocampus-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json` (typically at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp"
    }
  }
}
```

### Cursor

Open **Settings → Features → MCP** and add:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp"
    }
  }
}
```

## How It Works

```
Claude Code / Codex / Cursor
        │ (stdio)
        v
  hippocampus-mcp (MCP server)
        │ (HTTP)
        v
  hippocampus start (REST API on port 8321)
        │
  Storage / Embedder / Searcher
```

The MCP server is a thin wrapper that translates MCP tool calls into HTTP requests to the running Hippocampus service. All storage, embedding, and search logic stays in the main server.

## CLI Usage

You can also start the MCP server directly:

```bash
hippocampus mcp
```

This runs in stdio mode, suitable for direct integration with MCP clients.

## Example Workflow

Once configured, an AI agent can:

1. **Store context**: "Remember that the user prefers TypeScript over JavaScript"
2. **Recall later**: "What are the user's language preferences?"
3. **Organize**: Trigger consolidation to classify memories into partitions

The agent uses these tools naturally during conversation without explicit API calls.
