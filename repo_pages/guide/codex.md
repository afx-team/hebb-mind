---
description: "Give the Codex CLI persistent AI agent memory via MCP: install the hebb-mcp server so Codex can write, search, and consolidate memories across coding sessions."
---

# Codex Integration

Hebb Mind integrates with Codex through MCP tools. Codex can call `write_memory`, `search_memory`, `consolidate`, and `ingest_conversation` when useful.

## Prerequisites

- **Python >= 3.10** and `pipx` (or a venv) — see [Installation](./installation.md).
- The **`codex` CLI** must be on your `PATH`. `hebb codex install` registers the MCP server by running `codex mcp add`; without the `codex` CLI it cannot complete.

## Install

```bash
pipx install hebb-mind         # use `pipx upgrade hebb-mind` to update later
hebb setup                     # initialize + download the embedding model
hebb service install           # register + start the background service (MCP tools talk to it)
hebb codex install             # register Hebb Mind as a Codex MCP server (global-only)
```

No `pipx`? See [Installation → Install pipx](./installation.md#install-pipx-if-you-don-t-have-it).

`hebb service install` is required: the MCP tools forward to the local Hebb Mind service on `127.0.0.1:8321`. Skip it and Codex's first memory tool call fails with an opaque connection error.

Verify:

```bash
codex mcp list
```

## Use it in Codex

Once installed, just talk to Codex naturally — it decides when to call the memory tools. Concrete prompts that exercise each tool:

- **Store**: "Remember that I deploy with `make release` and prefer pnpm over npm."
- **Recall**: "What do you remember about how I deploy this project?"
- **Organize**: "Consolidate what you've learned about my preferences."

To nudge Codex toward durable memory, add project guidance (see [Capability Boundary](#capability-boundary) below).

## Native Codex Command

If you prefer to manage MCP servers directly, pass the **absolute path** to `hebb-mcp` (from `which hebb-mcp`) so it resolves regardless of how Codex is launched:

```bash
codex mcp add hebb -- "$(which hebb-mcp)"
```

For a remote Hebb Mind service, point `HEBB_URL` at the remote host:

```bash
codex mcp add hebb --env HEBB_URL=http://192.168.1.100:8321 -- "$(which hebb-mcp)"
```

## Capability Boundary

Codex uses MCP tools for explicit memory operations. Claude Code has an additional hooks layer that recalls memories on session lifecycle events and captures each completed turn to the working-memory inbox. Codex does not currently provide that hooks flow through this integration, so with Codex you (or your project guidance) drive the memory tools explicitly.

For best results, add project guidance that tells Codex when durable memory should be used:

```text
Use the Hebb Mind MCP server when durable user preferences, project facts, or cross-session decisions should be remembered or recalled.
```

## Uninstall

Codex stores MCP servers globally, so uninstall is global-only (there is no per-project scope):

```bash
hebb codex uninstall
```
