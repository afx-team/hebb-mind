---
description: "Connect Claude Code, Codex, Cursor, Windsurf, VS Code, and 15+ MCP-compatible clients to long-term AI agent memory — write, recall via hybrid vector+keyword search, and consolidate."
---

# MCP Integration

Hebb Mind provides an MCP (Model Context Protocol) server that exposes memory operations as tools. Any MCP-compatible client can use it directly. Below is the full quick-connect matrix — find your client and paste the snippet.

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

## Quick-Connect Matrix

::: tip Use the absolute path to `hebb-mcp`
All snippets below use `/absolute/path/to/hebb-mcp` as a placeholder. A **bare** `hebb-mcp` can fail to launch under GUI-launched apps (Claude Desktop, Cursor, Windsurf, LM Studio, etc.) that don't inherit your shell `PATH`. Run `which hebb-mcp` (Windows: `where hebb-mcp`) and replace the placeholder with the real path. The `hebb claude-code install` / `hebb codex install` commands already resolve this for you.
:::

If the Hebb Mind service runs on a remote host or non-default address, add an `env` block with `HEBB_URL`:

```json
"env": { "HEBB_URL": "http://192.168.1.100:8321" }
```

### Clients with first-class installers

#### Claude Code

```bash
hebb claude-code install --scope user   # hooks + MCP, absolute path auto-resolved
```

MCP-only (project-level `.mcp.json` or global `~/.claude.json`):

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Codex

```bash
hebb codex install   # project MCP + lifecycle hooks (default)
codex mcp list
```

Native Codex command:

```bash
codex mcp add hebb -- "$(which hebb-mcp)"
```

### Clients with config snippets

#### Amp

Amp CLI stores MCP servers in `.amp/settings.json` (project-scoped) or `~/.config/amp/settings.json` (global). Use the `amp mcp add` command:

```bash
amp mcp add hebb -- /absolute/path/to/hebb-mcp
```

Or edit `.amp/settings.json` directly:

```json
{
  "amp.mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Claude Desktop

Edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: `%APPDATA%\Claude\claude_desktop_config.json`). Claude Desktop is a GUI app — the absolute path is required:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Cline

Cline reads MCP config from `~/.cline/mcp.json` (CLI) or the VS Code extension's `cline_mcp_settings.json`. Open the Cline panel → MCP Servers icon → Configure tab → Configure MCP Servers, and add:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp",
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

#### Copilot (VS Code)

Copilot in VS Code uses the same `.vscode/mcp.json` as VS Code native MCP (see below). Alternatively, use the command palette:

```
MCP: Add Server → stdio → name: hebb → command: /absolute/path/to/hebb-mcp
```

#### Cursor

Edit `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project-scoped). Open via **Settings → Tools & MCP → New MCP Server**, or create the file:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Gemini CLI

Edit `~/.gemini/settings.json` and add a `mcpServers` entry:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Goose

Edit `~/.config/goose/config.yaml` (macOS/Linux) or `%APPDATA%\Block\goose\config\config.yaml` (Windows). Add under `extensions`:

```yaml
extensions:
  hebb:
    type: stdio
    name: hebb
    enabled: true
    cmd: /absolute/path/to/hebb-mcp
    args: []
    envs: {}
    timeout: 300
```

Or use the CLI wizard: `goose configure` → Add Extension → Stdio Extension → name: `hebb`, command: `/absolute/path/to/hebb-mcp`.

#### Kiro

Edit `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json` (user-level). Open via command palette: **Kiro: Open workspace MCP config**:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp",
      "args": [],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

#### LM Studio

LM Studio follows Cursor's `mcp.json` notation. The config file is at `~/.lmstudio/mcp.json` (macOS/Linux) or `%USERPROFILE%\.lmstudio\mcp.json` (Windows). Open via the **Program** tab → **Install → Edit mcp.json**:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### opencode

Edit `opencode.json` (project-level) or `~/.config/opencode/opencode.json` (global). Add under the `mcp` key:

```json
{
  "mcp": {
    "hebb": {
      "type": "local",
      "command": ["/absolute/path/to/hebb-mcp"],
      "enabled": true
    }
  }
}
```

Or use the CLI: `opencode mcp add` → name: `hebb`, type: `local`, command: `/absolute/path/to/hebb-mcp`.

#### VS Code (native MCP)

VS Code (1.102+) supports MCP natively. Edit `.vscode/mcp.json` (workspace) or open via command palette: **MCP: Open User Configuration**. Note: VS Code uses `"servers"` (not `"mcpServers"`):

```json
{
  "servers": {
    "hebb": {
      "type": "stdio",
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

Or from the command line:

```bash
code --add-mcp '{"name":"hebb","command":"/absolute/path/to/hebb-mcp"}'
```

#### Warp

Warp supports MCP servers via Settings → MCP (GUI). Add a new stdio server:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

#### Windsurf

Edit `~/.codeium/windsurf/mcp_config.json` (macOS/Linux) or `%USERPROFILE%\.codeium\windsurf\mcp_config.json` (Windows). Open via command palette: **Windsurf: Configure MCP Servers**:

```json
{
  "mcpServers": {
    "hebb": {
      "command": "/absolute/path/to/hebb-mcp"
    }
  }
}
```

### Other clients

The following clients support MCP but have UI-only or evolving configuration surfaces. Use the standard `mcpServers` JSON shape and paste it into the client's MCP settings UI:

| Client | Config location | Notes |
|--------|----------------|-------|
| **Antigravity** | Editor MCP settings (UI) | Google's agentic IDE; configure via Settings → MCP |
| **Factory** | Factory MCP config (UI) | Confirm format in Factory docs |
| **Junie (JetBrains)** | IDE MCP settings (UI) | JetBrains AI assistant; Settings → Tools → MCP |
| **Qodo Gen** | IDE plugin MCP config (UI) | VS Code extension; configure via plugin settings |

For each, add:

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
Claude Code / Codex / Cursor / Windsurf / VS Code / ...
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
