---
name: arxiv-search
description: Search arxiv for academic papers on a given topic, return structured summaries
user_invocable: true
arguments:
  - name: query
    description: The search topic or keywords
    required: true
---

# arxiv Paper Search

Search arxiv for academic papers related to the given query.

## Instructions

1. Use WebSearch to search for: `arxiv ${query}` and `arxiv ${query} 2024 2025 2026`
2. For each relevant paper found (up to 10), extract:
   - Title
   - Authors
   - Date
   - arxiv URL
   - Abstract summary (2-3 sentences)
   - Key contributions
3. Present results in a structured markdown table
4. Highlight papers most relevant to agent memory systems if applicable
5. Note any survey/review papers separately as they provide broader context
