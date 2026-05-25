# CLI Reference

Hebb Mind ships a single `hebb` command exposing all setup, server, integration, model, and configuration tasks.

```bash
hebb --version
hebb --help
```

## hebb setup

Prepare the default out-of-box environment: initialize the workspace if needed, pick an embedding model by content language, pick a HuggingFace download source by region, download and verify the model. Does **not** start the server.

```bash
hebb setup [--language auto|en|zh|multi] [--region auto|cn|global] [--profile default|fast|best]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--language` | `auto` | `en` → `BAAI/bge-large-en-v1.5`; `zh`/`multi` → `BAAI/bge-m3`; `auto` infers from system locale |
| `--region` | `auto` | `cn` uses `https://hf-mirror.com`; `global` uses HuggingFace official |
| `--profile` | `default` | `fast` favors small models; `best` favors quality |

After setup, run `hebb start`.

## hebb init

Initialize a workspace **without** network access. Creates `hebb.json`, the SQLite database, and an empty knowledge graph file.

```bash
hebb init [--dir DIR] [--force]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--dir DIR` | `HEBB_HOME` or `~/.hebb/` | Target directory |
| `--force` | -- | Overwrite existing config and reset SQLite storage |

**Created files:**

- `hebb.json` — configuration
- `hebb.db` — SQLite database (with the 5 default partitions)
- `knowledge_graph.json` — empty knowledge graph

## hebb start

Start the FastAPI server.

```bash
hebb start [--host HOST] [--port PORT] [--reload] [-d|--daemon]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | from config (`0.0.0.0`) | Bind address |
| `--port` | from config (`8321`) | Port |
| `--reload` | -- | Enable uvicorn auto-reload (dev) |
| `-d`, `--daemon` | -- | Run in the background; PID stored in `<workspace>/hebb.pid` |

If a server is already running at the resolved URL, the command exits without re-launching.

## hebb stop

Stop a running server (looks up the daemon PID, falls back to `lsof -ti :PORT`).

```bash
hebb stop [--url URL]
```

## hebb restart

Stop then start.

```bash
hebb restart [--host HOST] [--port PORT] [--reload] [-d|--daemon]
```

## hebb status

Health-check the running server and print scheduler job table.

```bash
hebb status [--url URL]
```

Sample output:

```
Server is running (v0.1.1)

Scheduler Jobs
┌──────────────────┬───────────────────────────┐
│ Job              │ Next Run                  │
├──────────────────┼───────────────────────────┤
│ consolidation_job│ 2026-04-18T18:00:00+08:00 │
│ forgetting_job   │ 2026-04-17T11:00:00+08:00 │
└──────────────────┴───────────────────────────┘
```

## hebb doctor

Run a one-shot health check covering Python version, config file, workspace, LLM, embedding model cache, web console assets, server reachability, and Claude Code / Codex MCP registration.

```bash
hebb doctor
```

The output is a Rich table with `[OK]` / `[WARN]` / `[FAIL]` status per check and a hint for each failure (e.g. *"Run: hebb model prefetch"*).

## hebb workspace

Print the resolved workspace directory. Resolution order:

1. `HEBB_HOME` environment variable
2. Parent directory of a `hebb.json` walked up from the current directory
3. `~/.hebb/` (global default)

```bash
hebb workspace
# /Users/you/.hebb
```

## hebb model

Inspect or prefetch the embedding model.

```bash
hebb model status
hebb model prefetch [--model MODEL_ID] [--region auto|cn|global]
```

`status` prints the configured provider, model, dimension, language strategy, download source, and whether the model is cached in the workspace and on the user HuggingFace cache.

`prefetch` downloads (or re-downloads) a model into the workspace `models/` directory, then loads it once to confirm dimension. With `--model` it also updates `embedding_provider`, `embedding_model`, and `embedding_dim` in `hebb.json`.

## hebb service

Install or uninstall a system service that auto-starts the server on boot. Detects the OS and writes a `systemd` unit (Linux) or `launchd` plist (macOS).

```bash
hebb service install
hebb service uninstall
```

After install:

| Platform | Inspect | Stop |
|----------|---------|------|
| Linux | `systemctl status hebb` / `journalctl -u hebb -f` | `systemctl stop hebb` |
| macOS | `launchctl print gui/$(id -u)/com.hebb.server` | `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hebb.server.plist` |

## hebb mcp

Start the MCP server in stdio mode. Requires the FastAPI server to be running at the configured URL — the MCP server is a thin wrapper that forwards `write_memory`, `search_memory`, and `consolidate` tool calls to it.

```bash
hebb mcp
```

Use this command in MCP-client config (Claude Desktop, Cursor, Continue) to register Hebb Mind.

## hebb cc

Claude Code integration. Installs hooks and registers the MCP server.

```bash
hebb cc install   [--scope project|user]   # default: project
hebb cc uninstall [--scope project|user]
hebb cc recall      # SessionStart hook
hebb cc write       # UserPromptSubmit hook
hebb cc stop        # Stop hook (consolidation + cleanup)
```

`install --scope project` writes to `.claude/` in the current directory; `--scope user` writes to `~/.claude/`.

## hebb codex

Codex CLI integration via `codex mcp add`/`remove`.

```bash
hebb codex install   [--scope user|project]   # default: user
hebb codex uninstall [--scope user|project]
```

Verify with `codex mcp list`.

## hebb config

Manage `hebb.json` from the CLI.

### config list

Print all configuration values (sensitive values masked).

```bash
hebb config list
```

### config get

Print one value. The synthetic key `workspace` returns the resolved workspace directory.

```bash
hebb config get llm_model
hebb config get workspace
```

### config set

Set one value. Type coercion happens automatically (`"true"` → `True`, `"8000"` → `8000`).

```bash
hebb config set llm_api_key sk-your-key
hebb config set llm_model openai/gpt-4o
hebb config set port 9000
hebb config set embedding_enabled false
hebb config set home /data/hebb
```

### config path

Print the active `hebb.json` path.

```bash
hebb config path
```
