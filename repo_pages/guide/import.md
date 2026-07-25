---
description: "Import OpenHands, OpenClaw, or HKUDS OpenHarness Markdown memory into Hebb Mind with one idempotent command."
---

# Import Agent Memory

Hebb Mind can migrate deterministic Markdown memory corpora from OpenHands, OpenClaw, and HKUDS OpenHarness. The command writes through the normal Hebb Mind API, so imported memories use the configured embedding provider and populate the same vector and full-text indexes as any other memory.

```bash
hebb import <source> <path>
```

Running the same command again against an unchanged corpus is safe. Hebb Mind stores a source identity and a hash of the cleaned content in memory metadata, then skips entries whose import key already exists.

## OpenHands

Pass a repository root, a `.openhands` directory, or a skills directory:

```bash
hebb import openhands /path/to/project
```

The importer discovers repository skills under `.openhands/skills/` and legacy microagents under `.openhands/microagents/`. It also accepts current Agent Skills layouts under `.agents/skills/`. Each Markdown skill becomes one `mem_procedural` memory tagged with `external-memory` and `openhands`.

## OpenClaw

Pass the OpenClaw workspace containing the memory files:

```bash
hebb import openclaw ~/.openclaw/workspace
```

Files are routed by purpose:

| Input | Hebb Mind partition |
|---|---|
| `MEMORY.md` | `mem_hippocampus` |
| `USER.md` | `mem_preference` |
| `SOUL.md` | `mem_procedural` |
| `memory/*.md` daily notes | `mem_episodic` |

## HKUDS OpenHarness

Pass a project root or its `.openharness/memory` directory:

```bash
hebb import hkuds /path/to/openharness-project
```

The importer reads top-level schema-v1 Markdown topic files and ignores the `MEMORY.md` index and entries marked `disabled: true`. It preserves the native memory ID, schema version, type, and category as import metadata. Workflow and procedure categories route to `mem_procedural`; user, feedback, project, and reference types route to their corresponding preference, episodic, or semantic partitions.

## Cleaning and updates

Every document passes through `clean_user_input()` before storage. System-tag blocks, fenced code dumps, pasted HTML, and long base64 blobs are removed; empty or greeting-only results are skipped.

The idempotency key includes both the stable source identity and the cleaned content hash. An unchanged file is skipped on re-import. If a file's meaningful content changes, the new revision is imported as a new memory while the previous memory remains available for explicit review or deletion. The command performs a one-time migration, not live or bidirectional synchronization.
