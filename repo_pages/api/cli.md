---
description: "Reference for the hebb CLI: set up AI agent memory, download embedding models, run the OS-managed background server, wire up MCP and Claude Code integrations, and manage config."
---

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
| `--language` | `auto` | Selects the content language; `auto` infers from system locale |
| `--region` | `auto` | `cn` uses `https://hf-mirror.com`; `global` uses HuggingFace official |
| `--profile` | `default` | Selects the embedding tier (see below) |

By default, `hebb setup` downloads a **small** embedding model (only if it is not already cached):

| Profile | English | Chinese / multilingual |
|---------|---------|------------------------|
| `default` | `all-MiniLM-L6-v2` (~90 MB) | `intfloat/multilingual-e5-small` (~470 MB) |
| `fast` | `all-MiniLM-L6-v2` (~90 MB) | `all-MiniLM-L6-v2` (~90 MB) |
| `best` | `BAAI/bge-large-en-v1.5` (1–2 GB) | `BAAI/bge-m3` (1–2 GB) |

The high-quality `best` tier (bge models) is **opt-in** and is not downloaded by default. Setup reuses an already-cached model and only downloads when the model is missing.

After setup, install the background service with `hebb service install`.

`hebb setup` also creates the workspace files on first run:

- `hebb.json` — configuration
- `hebb.db` — SQLite database (with the 5 default partitions)
- `knowledge_graph.json` — empty knowledge graph

## hebb service

Hebb Mind always runs as an OS-managed background service. There is no
foreground `start` command — the OS service manager (launchd on macOS,
systemd on Linux, Task Scheduler on Windows) owns the process.

```bash
hebb service install    [--scope user|system]
hebb service uninstall  [--scope user|system]
hebb service start      [--scope user|system]
hebb service stop       [--scope user|system]
hebb service restart    [--scope user|system]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--scope user` | ✔ | Per-user install, **no admin required**. macOS LaunchAgent / `systemctl --user` unit / per-user Scheduled Task |
| `--scope system` | -- | System-wide install. Requires `sudo` (macOS / Linux) or admin (Windows). Runs at boot for any user. |

After install, the host/port from `hebb.json` are used. To change them: edit
`hebb.json`, then `hebb service restart`.

| Platform | Inspect | Logs |
|----------|---------|------|
| macOS | `launchctl print gui/$(id -u)/com.hebb.server` | `tail -f /tmp/hebb.log /tmp/hebb.err` |
| Linux (user) | `systemctl --user status hebb` | `journalctl --user -u hebb -f` |
| Linux (system) | `sudo systemctl status hebb` | `journalctl -u hebb -f` |
| Windows | `schtasks /Query /TN "HebbMind" /FO LIST /V` | `%TEMP%\hebb.log` |

> **Linux note.** A `systemctl --user` service only runs while the user is
> logged in. To keep it running across logout and at boot, run
> `loginctl enable-linger $USER` once.

## hebb status

Show service-manager registration, server health, and scheduler jobs in one
combined view.

```bash
hebb status [--url URL]
```

Sample output:

```
launchd (com.hebb.server) (OS: Darwin)
  Installed: yes
  Running:   yes
  Logs:      tail -f /tmp/hebb.log /tmp/hebb.err

Server is running at http://127.0.0.1:8321 (v0.1.6)

Scheduler Jobs
┌──────────────────┬───────────────────────────┐
│ Job              │ Next Run                  │
├──────────────────┼───────────────────────────┤
│ consolidation_job│ 2026-04-18T18:00:00+08:00 │
│ forgetting_job   │ 2026-04-17T11:00:00+08:00 │
└──────────────────┴───────────────────────────┘
```

## hebb console

Open the Hebb Mind Web Console in the default browser. Health-checks the
local server first; aborts with a hint if it's not running.

```bash
hebb console            # open in browser
hebb console --print    # print URL only (CI / SSH friendly)
```

## hebb doctor

Run a one-shot health check covering Python version, config file, workspace, LLM, embedding model cache, web console assets, server reachability, and Claude Code / Codex MCP registration.

```bash
hebb doctor
```

The output is a Rich table with `[OK]` / `[WARN]` / `[FAIL]` status per check and a hint for each failure (e.g. *"Run: hebb model prefetch"*).

## hebb model

Inspect or prefetch the embedding model.

```bash
hebb model status
hebb model prefetch [--model MODEL_ID] [--region auto|cn|global]
```

`status` prints the configured provider, model, dimension, language strategy, download source, and whether the model is cached in the workspace and on the user HuggingFace cache.

`prefetch` downloads (or re-downloads) a model into the workspace `models/` directory, then loads it once to confirm dimension. With `--model` it also updates `embedding_provider`, `embedding_model`, and `embedding_dim` in `hebb.json`.

## hebb memory

Bulk operations on stored memories.

```bash
hebb memory reembed [--partition NAME] [--batch-size 64] [--dry-run] [--yes]
```

`reembed` walks every memory in storage (or just the named partition) and recomputes its embedding using the **currently configured** embedder. Use this after switching `embedding_model` or `embedding_dim` — the vector table is auto-reset on dimension change at the next service start, and `reembed` repopulates it.

- `--partition NAME` — limit to one partition (e.g. `mem_user`).
- `--batch-size N` — encode and write `N` memories per batch (default 64, max 512).
- `--dry-run` — count what would be re-embedded without writing.
- `--restart` — discard any existing checkpoint and start fresh from the first memory.
- `-y / --yes` — skip the confirmation prompt. Required in non-interactive shells.

A checkpoint file (`<workspace>/reembed.checkpoint.json`) is written every ~32 memories. An interrupted run can be **resumed by re-invoking the command** — only the remaining memories are processed. The checkpoint is automatically deleted on successful completion, and automatically discarded if the embedder model / dim / partition scope changes between runs.

See [Switch the Embedding Model](../guide/switch-embedding-model.md) for the full workflow.

## hebb mcp

MCP server commands.

```bash
hebb mcp serve
```

`serve` starts the MCP stdio server. Requires the FastAPI server to be
running at the configured URL — the MCP server is a thin wrapper that
forwards `write_memory`, `search_memory`, and `consolidate` tool calls to
it. Use this in MCP-client config (Claude Desktop, Cursor, Continue) to
register Hebb Mind.

## hebb claude-code

Claude Code integration. Installs hooks and registers the MCP server.

```bash
hebb claude-code install   [--scope project|user]   # default: project
hebb claude-code uninstall [--scope project|user]
hebb claude-code recall      # SessionStart hook — recall cross-session memories
hebb claude-code prompt      # UserPromptSubmit hook — recall prompt-relevant memories
hebb claude-code stop        # Stop hook — record the last turn into the workspace
```

`install --scope project` writes to `.claude/` in the current directory; `--scope user` writes to `~/.claude/`.

The hooks are recall-and-capture, not consolidation. `recall` and `prompt` **read** memories and inject them into the session; `stop` **captures** the last user + assistant turn from the transcript (`source: hook:stop`, deduped per `session_id` + turn index). Consolidation does not run on `stop` — it runs on the `consolidation_time` schedule or via `POST /api/v1/admin/consolidate`.

## hebb codex

Native Codex integration with MCP plus `SessionStart`, `UserPromptSubmit`,
and `Stop` hooks. Project scope writes `.codex/config.toml` and
`.codex/hooks.json`; user scope uses `codex mcp add` and
`~/.codex/hooks.json`.

```bash
hebb codex install   [--scope project|user]   # default: project; current project
hebb codex uninstall [--scope project|user]   # default: project; current project
hebb codex recall    # SessionStart hook entry point
hebb codex prompt    # UserPromptSubmit hook entry point
hebb codex stop      # Stop hook entry point
```

`--scope user` means user-level configuration for the current OS user and
applies to all of that user's Codex projects. Omitting it is equivalent to
`--scope project`, which writes only the current directory's `.codex/`.

Verify MCP with `codex mcp list` and review hooks with `/hooks`.

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
