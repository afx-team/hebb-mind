# afx-team GitHub Organization Analysis

> Generated: 2026-04-15 | Project: hippocampus

## Organization Overview

- **URL**: https://github.com/afx-team
- **Status**: New/emerging organization — limited public information available from search
- **Focus**: To be established with the hippocampus project as a flagship

## Recommendations for Hippocampus Project

### Project Positioning

Given the competitive landscape (Mem0, Letta, Zep, Cognee), hippocampus should differentiate by:

1. **Neuroscience-first design** — Not just using brain metaphors, but implementing actual cognitive memory mechanisms (consolidation, decay, interference, emotional tagging)
2. **Lightweight & embeddable** — While competitors require PostgreSQL, Neo4j, or cloud services, hippocampus should work with SQLite out of the box
3. **Framework-agnostic** — Clean Python API that works with any LLM provider or agent framework
4. **Research-friendly** — Easy to experiment with different memory architectures, not locked into one approach

### Recommended Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.10+ | AI/ML ecosystem standard |
| **Package Manager** | uv / poetry | Modern Python packaging |
| **Default Storage** | SQLite + sqlite-vec | Zero-config, embedded, vector search built-in |
| **Optional Storage** | PostgreSQL+pgvector, Qdrant, ChromaDB | Pluggable backends for scale |
| **Graph** | NetworkX (embedded) / Neo4j (optional) | Start simple, scale later |
| **Embeddings** | sentence-transformers (local) / OpenAI (API) | Pluggable embedding providers |
| **LLM Integration** | litellm or raw HTTP | Provider-agnostic LLM calls |
| **Testing** | pytest + pytest-asyncio | Standard Python testing |
| **Docs** | mkdocs-material | Clean documentation site |
| **CI/CD** | GitHub Actions | Standard for OSS |

### Suggested Repo Structure

```
hippocampus/
├── src/
│   └── hippocampus/
│       ├── __init__.py
│       ├── core/
│       │   ├── memory.py          # Core memory abstractions
│       │   ├── types.py           # Memory types (episodic, semantic, procedural)
│       │   └── retrieval.py       # Retrieval strategies
│       ├── storage/
│       │   ├── base.py            # Storage interface
│       │   ├── sqlite.py          # Default SQLite backend
│       │   ├── postgres.py        # PostgreSQL backend
│       │   └── qdrant.py          # Qdrant backend
│       ├── consolidation/
│       │   ├── consolidator.py    # Memory consolidation engine
│       │   ├── decay.py           # Forgetting/decay mechanisms
│       │   └── importance.py      # Importance scoring
│       ├── graph/
│       │   ├── knowledge.py       # Knowledge graph memory
│       │   └── temporal.py        # Temporal graph support
│       ├── integrations/
│       │   ├── langchain.py       # LangChain adapter
│       │   ├── llamaindex.py      # LlamaIndex adapter
│       │   └── openai.py          # OpenAI function calling
│       └── server/
│           └── api.py             # REST API server (optional)
├── tests/
├── benchmarks/                    # Memory benchmarks
├── examples/
├── docs/
├── pyproject.toml
├── README.md
└── LICENSE (Apache 2.0 or MIT)
```

### Naming Conventions

- Package: `hippocampus`
- PyPI: `hippocampus-memory` or `afx-hippocampus`
- Repo: `afx-team/hippocampus`
- Imports: `from hippocampus import Memory, EpisodicMemory, SemanticMemory`

### Differentiation Strategy

| Aspect | Competitors | Hippocampus |
|--------|------------|-------------|
| Memory model | Ad-hoc | Neuroscience-grounded |
| Default storage | External DB required | SQLite (zero-config) |
| Memory decay | Not supported | Built-in (Ebbinghaus curve) |
| Consolidation | Manual/none | Automatic (sleep-like cycles) |
| Memory types | Flat or 2-level | Full CoALA taxonomy |
| Procedural memory | Weak/none | First-class (skill library) |
| Deployment | Server/cloud | Embeddable + server mode |
| Research use | Closed architecture | Pluggable, experimentable |
