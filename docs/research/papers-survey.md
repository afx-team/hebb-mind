# Research Papers Survey

This page summarizes the key academic papers that informed the design of Hippocampus. For detailed notes on each paper, see the [full survey](../papers/agent-memory-papers-survey.md).

## Foundational Papers

### Generative Agents: Interactive Simulacra of Human Behavior

**Park et al., 2023 (UIST 2023)** | [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)

Introduced the **memory stream** architecture and the retrieval formula that combines three signals:

```
score = alpha * recency + beta * importance + gamma * relevance
```

- **Recency** -- exponential decay since last access
- **Importance** -- LLM-rated 1-10 score
- **Relevance** -- embedding cosine similarity

This paper is the most cited work in agent memory research. The recency-importance-relevance retrieval formula has become the de facto standard and is directly implemented in Hippocampus.

**Impact on Hippocampus**: The three-signal scoring model is the foundation of our retrieval system.

---

### MemGPT: Towards LLMs as Operating Systems

**Packer et al., 2023** | [arXiv:2310.08560](https://arxiv.org/abs/2310.08560)

Proposed treating the LLM context window like an OS managing virtual memory:

- **Main context (RAM)** -- system prompt + core memory blocks + FIFO message queue
- **Archival storage (disk)** -- vector-indexed long-term storage
- **Recall storage** -- searchable conversation history

The key innovation is **agent-driven memory management**: the model decides when and what to retrieve via function calls (`core_memory_append`, `archival_memory_search`, etc.). This shifted the paradigm from passive to active memory management.

**Impact on Hippocampus**: Inspired our consolidation agent approach, where an LLM actively processes and organizes memories rather than simply storing them passively.

---

### Cognitive Architectures for Language Agents (CoALA)

**Sumers et al., 2023** | [arXiv:2309.02427](https://arxiv.org/abs/2309.02427)

Provided a systematic framework for categorizing language agent architectures, defining a memory taxonomy rooted in cognitive science:

- **Working memory** -- current context window contents
- **Episodic memory** -- past experiences and interactions
- **Semantic memory** -- world knowledge and facts
- **Procedural memory** -- learned skills, code, action patterns

**Impact on Hippocampus**: Our five-partition system (hippocampus, semantic, episodic, preference, procedural) is directly derived from the CoALA taxonomy, with the addition of a "preference" partition and the "hippocampus" working memory inbox.

---

### Zep / Graphiti: Temporal Knowledge Graphs

**Zep Team** | [GitHub: getzep/graphiti](https://github.com/getzep/graphiti)

Introduced temporal knowledge graphs for agent memory:

- Entities and relationships evolve over time
- Bi-temporal data model (valid time + transaction time)
- Graph RAG for retrieval
- Automated fact extraction from conversations

**Impact on Hippocampus**: Inspired our tag-based knowledge graph and the use of graph traversal as a retrieval path alongside vector and keyword search.

## Additional Influences

| Paper | Key Contribution | Relevance |
|-------|-----------------|-----------|
| **Reflexion** (Shinn et al., 2023) | Verbal reinforcement learning from self-reflection | Episodic memory as learning mechanism |
| **Voyager** (Wang et al., 2023) | Skill library as procedural memory | Code-based procedural memory patterns |
| **SCM** (2024) | Experience shortcuts for self-evolving agents | Memory compression and pattern reuse |

## Further Reading

- [Full papers survey](../papers/agent-memory-papers-survey.md) -- detailed notes on 10+ papers
- [Open-source projects analysis](./github-projects.md) -- how these ideas are implemented in practice
