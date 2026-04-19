# MCP Integration

Hippocampus provides an MCP (Model Context Protocol) server that exposes memory operations as tools. Claude Code, Cursor, and other MCP-compatible clients can use it directly.

## Installation

```bash
pip install afx-hippocampus[mcp]
```

## Prerequisites

The hippocampus service must be running:

```bash
hippocampus init     # first time only
hippocampus start
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `write_memory` | Write a memory to the hippocampus inbox | `content`, `tags?`, `importance?` |
| `search_memory` | Hybrid retrieval (vector + keyword + graph) | `query`, `top_k?` |
| `consolidate` | Trigger memory consolidation | none |

## Configuration

### Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

Or add globally in `~/.claude.json`:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

### Cursor

Add to Cursor MCP settings:

```json
{
  "mcpServers": {
    "hippocampus": {
      "command": "hippocampus-mcp",
      "cwd": "/path/to/your/project"
    }
  }
}
```

::: tip
`cwd` must point to the directory containing `hippocampus.json`. The MCP server reads this config to find the running service's host and port.
:::

## How It Works

```
Claude Code / Cursor
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
