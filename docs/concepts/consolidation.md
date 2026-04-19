# Memory Consolidation

Memory consolidation is the process by which raw memories in the working inbox (`mem_hippocampus`) are analyzed, classified, and moved into long-term partitions. This mirrors how the biological hippocampus consolidates short-term memories during sleep.

## How It Works

The consolidation agent performs five steps for each unprocessed memory:

1. **Pick** -- selects unprocessed memories from `mem_hippocampus`
2. **Recall** -- uses Agentic RAG to retrieve related historical memories from all partitions, providing context for classification
3. **Classify** -- LLM determines the appropriate partition:
   - `mem_semantic` -- facts and knowledge
   - `mem_episodic` -- events and history
   - `mem_preference` -- likes and dislikes
   - `mem_procedural` -- skills and how-to knowledge
4. **Resolve conflicts** -- detects contradictions with existing memories and resolves them (newer information typically supersedes older)
5. **Extract tags** -- identifies meaningful tags and adds them as nodes/edges to the knowledge graph

## Partitions

Hippocampus ships with five built-in partitions inspired by cognitive science:

| Partition | Purpose | Example |
|-----------|---------|---------|
| `mem_hippocampus` | Working memory inbox | All new memories before processing |
| `mem_semantic` | Facts and knowledge | "Python 3.12 was released in October 2023" |
| `mem_episodic` | Events and history | "User deployed v2.0 on March 15" |
| `mem_preference` | Likes and dislikes | "User prefers dark mode" |
| `mem_procedural` | Skills and how-to | "To deploy, run `make deploy`" |

### Custom Partitions

You can create additional partitions for your use case:

```bash
curl -X POST http://localhost:8321/api/v1/partitions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "mem_project",
    "name": "Project Context",
    "description": "Current project knowledge and context"
  }'
```

System partitions (`mem_hippocampus`, `mem_semantic`, `mem_episodic`, `mem_preference`, `mem_procedural`) cannot be deleted.

## Scheduling

Consolidation runs automatically on a periodic schedule. The interval is configured via `consolidation_interval_seconds` (default: 3600 seconds / 1 hour).

```bash
# Run consolidation every 30 minutes
hippocampus config set consolidation_interval_seconds 1800
```

## Manual Trigger

Trigger consolidation immediately via the admin API:

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

This is useful for development, testing, or when you want immediate processing after a batch import.

## Conflict Resolution

When the consolidation agent detects a contradiction between a new memory and an existing one, it resolves the conflict based on:

- **Temporal precedence** -- newer information generally supersedes older
- **Importance score** -- higher-importance memories are given more weight
- **LLM judgment** -- the LLM evaluates the conflict in context and decides whether to update, merge, or keep both memories

For example, if the system contains "User prefers dark mode" and a new memory states "User switched to light mode," the consolidation agent will update or replace the older preference.
