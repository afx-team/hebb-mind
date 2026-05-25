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

## Configuration

The MCP server automatically discovers the service address from `hebb.json`. For the common case (service running locally), no configuration is needed — just add the command.

If the service runs on a remote host or non-default address, set `HEBB_URL`:

### Claude Code

Recommended:

```bash
hebb claude-code install --scope user
```

MCP-only:

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "hebb-mcp"
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
      "command": "hebb-mcp",
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
hebb codex install --scope user
codex mcp list
```

Native Codex command:

```bash
codex mcp add hebb -- hebb-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json` (typically at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "hebb": {
      "command": "hebb-mcp"
    }
  }
}
```

### Cursor

Open **Settings → Features → MCP** and add:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "hebb-mcp"
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
