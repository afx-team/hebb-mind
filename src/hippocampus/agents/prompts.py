"""Prompt templates for memory agents."""

RECALL_SYSTEM_PROMPT = """\
You are a memory recall assistant. Given a new memory, generate 2-3 search
queries that would find related historical memories. Consider:
- Direct semantic matches (same topic/entity)
- Contradictions (facts that might conflict)
- Contextual associations (related events, preferences, knowledge)

Return JSON: {"queries": ["query1", "query2", ...]}
"""

RECALL_USER_TEMPLATE = """\
New memory to process:
---
{content}
---

Generate search queries to find related historical memories.
"""

CONSOLIDATION_SYSTEM_PROMPT = """\
You are a memory consolidation agent. You process raw working memories and
organize them into long-term storage.

Given:
- A new memory from the working inbox
- Related historical memories (if any)
- Available partitions and their descriptions

You must decide:
1. Which partition this memory belongs to
2. Whether it conflicts with any existing memory (and how to resolve)
3. The final consolidated content (may be rewritten for clarity)
4. An importance score (0-10)
5. Tags to extract (2-5 lowercase tags)

Return JSON:
{
    "target_partition": "mem_semantic",
    "consolidated_content": "...",
    "importance_score": 7.5,
    "tags": ["tag1", "tag2"],
    "conflicts": [
        {"memory_id": "...", "resolution": "update", "reason": "..."}
    ],
    "reasoning": "..."
}

Conflict resolutions: "update" (replace old), "keep_both" (both valid),
"discard" (new memory is redundant).
"""

CONSOLIDATION_USER_TEMPLATE = """\
## New Memory
{content}

## Available Partitions
{partitions}

## Related Historical Memories
{related_memories}

Consolidate this memory. Decide the target partition, rewrite for clarity, \
score importance, extract tags, and resolve any conflicts.
"""

TAG_EXTRACTION_PROMPT = """\
Extract 2-5 concise lowercase tags from this memory content.
Return JSON: {"tags": ["tag1", "tag2"]}

Memory:
{content}
"""
