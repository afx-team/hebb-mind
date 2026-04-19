---
layout: home

hero:
  name: Hippocampus
  text: Agent Memory Framework
  tagline: Give your AI agents a real memory — neuroscience-inspired consolidation, retrieval, and forgetting.
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/afx-team/hippocampus

features:
  - icon: "\U0001F9E0"
    title: Memory Consolidation
    details: Automatic agent classifies memories into semantic, episodic, preference, and procedural partitions — just like the human brain.
  - icon: "\U0001F504"
    title: Dynamic Forgetting
    details: TTL formula inspired by Ebbinghaus — frequently accessed, high-importance memories live longer. Neglected memories fade naturally.
  - icon: "\U0001F50D"
    title: Hybrid Search
    details: Three-path retrieval (vector + keyword + knowledge graph) with recency, importance, and relevance scoring.
  - icon: "\U0001F310"
    title: Knowledge Graph
    details: Tags extracted during consolidation form a graph of connected concepts. Explore relationships visually in the Web Console.
  - icon: "\u26A1"
    title: Zero-Config Start
    details: "SQLite backend: hippocampus init && hippocampus start is all you need. Upgrade to PostgreSQL for production."
  - icon: "\U0001F5A5"
    title: Web Console
    details: Built-in dark-themed dashboard for memory CRUD, semantic search, partition management, and graph visualization.
---

<div class="vp-doc" style="max-width: 688px; margin: 48px auto; padding: 0 24px;">

## Quick Install

```bash
pip install afx-hippocampus
hippocampus init
hippocampus start
# Open http://localhost:8321/
```

## Comparison

| Feature | Mem0 | Letta | Zep | **Hippocampus** |
|---------|------|-------|-----|-----------------|
| Memory consolidation | - | - | - | Automatic |
| Forgetting / decay | - | - | Implicit | Dynamic TTL |
| Knowledge graph | - | - | Partial | Built-in |
| Zero-config deploy | - | - | - | SQLite |
| Multi-model | Partial | Partial | Partial | Via LiteLLM |
| Web management UI | - | Partial | Partial | Built-in |

</div>
