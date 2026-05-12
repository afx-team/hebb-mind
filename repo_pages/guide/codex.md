# Codex Integration

Hippocampus integrates with Codex through MCP tools. Codex can call `write_memory`, `search_memory`, `consolidate`, and `ingest_conversation` when useful.

## Install

```bash
pip install -U afx-hippocampus
hippocampus setup
hippocampus codex install --scope user
```

Verify:

```bash
codex mcp list
```

## Native Codex Command

If you prefer to manage MCP servers directly:

```bash
codex mcp add hippocampus -- hippocampus-mcp
```

For a remote Hippocampus service:

```bash
codex mcp add hippocampus --env HIPPOCAMPUS_URL=http://127.0.0.1:8321 -- hippocampus-mcp
```

## Capability Boundary

Codex uses MCP tools for explicit memory operations. Claude Code has an additional hooks layer that can automatically write and recall memories on session lifecycle events. Codex does not currently provide the same hooks flow through this integration.

For best results, add project guidance that tells Codex when durable memory should be used:

```text
Use the Hippocampus MCP server when durable user preferences, project facts, or cross-session decisions should be remembered or recalled.
```

## Uninstall

```bash
hippocampus codex uninstall --scope user
```
