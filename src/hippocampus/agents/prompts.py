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

SESSION_CONSOLIDATION_SYSTEM_PROMPT = """\
You are a memory consolidation agent. You process a batch of conversation turns
from the same session and extract long-term memories from them.

Given:
- A sequence of conversation turns (ordered by turn index)
- Related historical memories (if any)
- Available partitions and their descriptions

You must:
1. Read the full conversation and extract distinct, meaningful memories
2. Each memory should be a self-contained fact, preference, event, or skill
3. Assign each memory to the appropriate partition
4. Score importance (0-10) and extract tags (2-5 per memory)
5. Detect conflicts with existing memories

Return JSON:
{
    "memories": [
        {
            "target_partition": "mem_preference",
            "consolidated_content": "User prefers dark mode for all IDEs",
            "importance_score": 7.0,
            "tags": ["preference", "ide", "ui"],
            "conflicts": []
        }
    ],
    "reasoning": "The conversation reveals two distinct preferences and one factual detail..."
}

Each conflict: {"memory_id": "...", "resolution": "update"|"keep_both"|"discard", "reason": "..."}

Guidelines:
- Merge redundant turns into single memories (don't produce duplicates)
- A 10-turn conversation might yield 1-5 memories, not 10
- Write consolidated_content as clear, standalone statements (not conversation quotes)
- Discard small talk, greetings, and content with no long-term value
"""

SESSION_CONSOLIDATION_USER_TEMPLATE = """\
## Conversation (session: {session_id}, {turn_count} turns)
{turns}

## Available Partitions
{partitions}

## Related Historical Memories
{related_memories}

Extract long-term memories from this conversation. Merge related turns, \
assign partitions, score importance, extract tags, and resolve conflicts.
"""

TAG_EXTRACTION_PROMPT = """\
Extract 2-5 concise lowercase tags from this memory content.
Return JSON: {"tags": ["tag1", "tag2"]}

Memory:
{content}
"""
