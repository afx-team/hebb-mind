# Open-Source Agent Memory Projects

This page summarizes the open-source agent memory projects analyzed during the research phase of Hippocampus. For full analysis details, see the [complete report](../analysis/github-agent-memory-projects.md).

## Projects Analyzed

### Mem0 (mem0ai/mem0)

[GitHub](https://github.com/mem0ai/mem0) | ~25k+ stars

**Approach**: Hybrid storage with vector DB (Qdrant, Pinecone, ChromaDB) + graph DB (Neo4j) + key-value store.

**Key features**:
- LLM-in-the-loop: the model decides what to remember, update, or forget
- Multi-level memory scopes (user, session, agent)
- Graph memory for relational knowledge
- Built-in conflict resolution

**Strengths**: Simple API, production-ready server mode, strong ecosystem integrations (OpenAI, LangChain, LlamaIndex, CrewAI).

**Gaps**: Heavy LLM dependency for all operations (cost/latency), no built-in forgetting mechanism, limited procedural memory support.

---

### Letta (formerly MemGPT) (letta-ai/letta)

[GitHub](https://github.com/letta-ai/letta) | ~15k+ stars

**Approach**: OS-inspired memory hierarchy with agent-driven management.

**Key features**:
- Agent actively manages its own memory via function calls
- Core memory (always in context) + archival memory (vector-indexed) + recall memory (conversation history)
- Multi-agent support with shared memory blocks
- Agent Development Environment (ADE)

**Strengths**: Most sophisticated memory management model, strong theoretical foundation (MemGPT paper), excellent for long-running agents.

**Gaps**: Higher complexity and learning curve, requires more LLM calls per turn, PostgreSQL dependency.

---

### Zep + Graphiti (getzep/zep, getzep/graphiti)

[GitHub (Zep)](https://github.com/getzep/zep) | [GitHub (Graphiti)](https://github.com/getzep/graphiti) | ~3k+ stars each

**Approach**: Temporal knowledge graph with graph-first architecture.

**Key features**:
- Graphiti: temporal knowledge graph engine with bi-temporal data model
- Automated fact extraction from conversations
- Entity resolution and relationship tracking
- Graph RAG for retrieval

**Strengths**: Strongest relational/graph memory model, temporal awareness is a unique differentiator, Graphiti is usable standalone.

**Gaps**: Neo4j dependency (operational complexity), open-source version more limited than cloud offering.

---

### Cognee (topoteretes/cognee)

[GitHub](https://github.com/topoteretes/cognee) | ~3k+ stars

**Approach**: Deterministic knowledge engine with pluggable storage.

**Key features**:
- Multi-format data ingestion (PDF, audio, video, text, code)
- Automatic knowledge graph construction
- Deterministic pipelines (no LLM randomness in processing)
- Supports Qdrant, Weaviate, PGVector, Neo4j, FalkorDB, Milvus

**Strengths**: Most flexible storage backends, deterministic processing reduces hallucination risk.

**Gaps**: More of a knowledge engine than an agent memory system, API still evolving.

---

### LangChain Memory

[GitHub](https://github.com/langchain-ai/langchain) | Part of LangChain (~100k+ stars)

**Approach**: Modular memory components within the LangChain agent framework.

**Key features**:
- Multiple memory types: buffer, summary, sliding window, knowledge graph, vector store, entity
- Composable with chains and agents
- LangGraph integration for stateful workflows

**Strengths**: Largest ecosystem, most tutorials and examples, simple abstractions.

**Gaps**: Memory types are relatively simple, conversation-centric design, less suitable as a standalone memory system.

## Comparative Summary

| Feature | Mem0 | Letta | Zep | Cognee | **Hippocampus** |
|---------|------|-------|-----|--------|-----------------|
| Memory consolidation | LLM-driven | Agent-driven | Automated | Pipeline | Agentic RAG |
| Forgetting/decay | Manual | None | Implicit | None | Dynamic TTL |
| Knowledge graph | Neo4j (optional) | None | Neo4j (core) | Pluggable | NetworkX (built-in) |
| Storage backends | Qdrant, Pinecone, etc. | PostgreSQL | Neo4j | 6+ options | SQLite, PostgreSQL |
| Zero-config setup | No | No | No | No | Yes (SQLite) |
| Memory taxonomy | User/session/agent | Core/archival/recall | Episodic/semantic | Knowledge graph | 5 brain-inspired partitions |

## Key Takeaways for Hippocampus

1. **Simple defaults, powerful options** -- unlike Mem0 and Zep which require external databases, Hippocampus works out of the box with SQLite
2. **Active memory management** -- like Letta, our consolidation agent actively processes memories rather than passively storing them
3. **Built-in forgetting** -- no other major project implements dynamic, formula-based memory decay
4. **Knowledge graph without Neo4j** -- NetworkX + JSON gives us graph capabilities without operational complexity
5. **Cognitive science foundation** -- the partition system is grounded in the CoALA taxonomy, not ad-hoc categories
