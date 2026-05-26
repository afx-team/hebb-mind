# Codex Integration

Hebb Mind integrates with Codex through MCP tools. Codex can call `write_memory`, `search_memory`, `consolidate`, and `ingest_conversation` when useful.

## Install

```bash
pipx install hebb-mind         # use `pipx upgrade hebb-mind` to update later
hebb setup
hebb codex install --scope user
```

No `pipx`? See [Installation → Install pipx](./installation.md#install-pipx-if-you-don-t-have-it).

Verify:

```bash
codex mcp list
```

## Native Codex Command

If you prefer to manage MCP servers directly:

```bash
codex mcp add hebb -- hebb-mcp
```

For a remote Hebb Mind service:

```bash
codex mcp add hebb --env HEBB_URL=http://127.0.0.1:8321 -- hebb-mcp
```

## Capability Boundary

Codex uses MCP tools for explicit memory operations. Claude Code has an additional hooks layer that can automatically write and recall memories on session lifecycle events. Codex does not currently provide the same hooks flow through this integration.

For best results, add project guidance that tells Codex when durable memory should be used:

```text
Use the Hebb Mind MCP server when durable user preferences, project facts, or cross-session decisions should be remembered or recalled.
```

## Uninstall

```bash
hebb codex uninstall --scope user
```
