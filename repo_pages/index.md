---
layout: home

hero:
  name: Hippocampus
  text: Agent Memory Framework
  tagline: Give your AI agents a real memory — neuroscience-inspired consolidation, retrieval, and forgetting.
  actions:
    - theme: brand
      text: Get Started
      link: /quick-start
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

<div class="vp-doc" style="max-width: 780px; margin: 48px auto; padding: 0 24px;">

## Quick Install

```bash
pip install afx-hippocampus
hippocampus init
hippocampus start
# Open http://localhost:8321/
```

## Architecture

<table style="width:100%; border:none; border-collapse:collapse;">
<tr>
<td align="center" colspan="5" style="padding:6px 14px; background:#1a1a2e; border-radius:8px; color:#e0e0e0; font-weight:600;">
API &middot; MCP &middot; CLI
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:18px; color:#555;">▼</td></tr>
<tr>
<td align="center" colspan="5" style="padding:10px 18px; background:#16213e; border-radius:8px;">
<b style="color:#00d2ff; font-size:16px;">HIPPOCAMPUS</b><br/>
<span style="color:#888; font-size:12px;">Working Memory Inbox</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; color:#555; padding:4px 0;">▼&nbsp; Consolidation Agent <span style="color:#666; font-size:11px;">(Agentic RAG &middot; Classify &middot; Conflict Resolve &middot; Tag Extract)</span></td></tr>
<tr>
<td align="center" style="padding:8px 12px; background:#1b4332; border-radius:6px; min-width:100px;">
<b style="color:#52b788;">SEMANTIC</b><br/><span style="color:#888; font-size:11px;">Facts & Knowledge</span>
</td>
<td align="center" style="padding:8px 12px; background:#3c1642; border-radius:6px; min-width:100px;">
<b style="color:#c77dff;">EPISODIC</b><br/><span style="color:#888; font-size:11px;">Events & History</span>
</td>
<td align="center" style="padding:8px 12px; background:#6b2d5b; border-radius:6px; min-width:100px;">
<b style="color:#ff6b6b;">PREFERENCE</b><br/><span style="color:#888; font-size:11px;">Likes & Dislikes</span>
</td>
<td align="center" style="padding:8px 12px; background:#2d3a4a; border-radius:6px; min-width:100px;">
<b style="color:#4ecdc4;">PROCEDURAL</b><br/><span style="color:#888; font-size:11px;">Skills & How-to</span>
</td>
<td align="center" style="padding:8px 12px; background:#3d3d3d; border-radius:6px; min-width:100px;">
<b style="color:#aaa;">CUSTOM</b><br/><span style="color:#888; font-size:11px;">Your Partitions</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; padding:6px 0;">
<span style="color:#555;">▼</span>&nbsp;
<span style="color:#666; font-size:12px;">Hybrid Retrieval</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">Knowledge Graph</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">Forgetting (Dynamic TTL)</span>
</td></tr>
</table>

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