---
description: "Give Codex automatic persistent memory with native lifecycle hooks and MCP: project-scoped recall, turn capture, search, write, and consolidation."
---

# Codex Integration

Hebb Mind integrates with Codex through native lifecycle hooks and MCP.
`SessionStart` recalls cross-session context, `UserPromptSubmit` searches for
prompt-relevant memories, and `Stop` captures the completed turn. MCP also
exposes `write_memory`, `search_memory`, `consolidate`, and
`ingest_conversation` for explicit operations.

## Prerequisites

- The **`codex` CLI** must be on `PATH`.
- Install and initialize Hebb Mind.
- Install the background service because hooks and MCP forward requests to
  the local REST API.

## Project installation

Run this from the repository you want to equip with memory:

```bash
pipx install hebb-mind
hebb setup
hebb service install
hebb codex install
```

Project scope is the default. The installer writes:

- `.codex/config.toml` — the project-scoped `hebb` MCP server
- `.codex/hooks.json` — automatic recall and turn-capture hooks

Existing unrelated Codex config and hooks are preserved. Re-running the
installer replaces only Hebb-managed entries.

`--scope` controls where the integration is written:

| Command | Applies to | Writes |
|---|---|---|
| `hebb codex install` | Current project | `.codex/config.toml` and `.codex/hooks.json` |
| `hebb codex install --scope project` | Current project | Same as above |
| `hebb codex install --scope user` | Every Codex project for the current OS user | User-level Codex MCP config and `~/.codex/hooks.json` |

## Activate and verify

Codex loads project configuration only for trusted projects, and command
hooks require explicit review. Start a new Codex thread in the project, then:

```text
/hooks
```

Review and trust the three Hebb hooks. Verify MCP from a terminal:

```bash
codex mcp list
```

## User-wide installation

To make Hebb Mind available in every project:

```bash
hebb codex install --scope user
```

This registers MCP through `codex mcp add` and writes hooks to
`~/.codex/hooks.json`. User hooks also require review through `/hooks`.

## Lifecycle behavior

| Event | Hebb command | Behavior |
|---|---|---|
| `SessionStart` | `hebb codex recall` | Adds recent cross-session context and preferences |
| `UserPromptSubmit` | `hebb codex prompt` | Adds memories relevant to the current prompt |
| `Stop` | `hebb codex stop` | Parses the Codex rollout and writes the completed turn |

Hook failures degrade to a no-op so a stopped Hebb service does not block
Codex. The next hook or MCP launch asks the installed OS service manager to
start Hebb Mind.

## MCP tools

You can still request explicit memory operations:

- “Remember that this project uses pnpm, not npm.”
- “Search long-term memory for the authentication decision.”
- “Consolidate the memories collected today.”

Project guidance in `AGENTS.md` can define which decisions should be stored,
but normal cross-session recall and turn capture no longer depend on the
model deciding to call an MCP tool.

## Remote Hebb Mind service

For a remote service, user-level MCP can still be registered directly:

```bash
codex mcp add hebb \
  --env HEBB_URL=http://192.168.1.100:8321 \
  -- "$(which hebb-mcp)"
```

If lifecycle hooks should use the same remote service, export `HEBB_URL` in
the environment that launches Codex.

## Uninstall

Remove the current project's integration:

```bash
hebb codex uninstall
```

Remove the user-wide integration:

```bash
hebb codex uninstall --scope user
```
