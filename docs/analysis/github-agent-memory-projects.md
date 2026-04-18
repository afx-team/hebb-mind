# GitHub Agent Memory Projects Survey

> Generated: 2026-04-15 | Project: hippocampus

## 1. Mem0 (mem0ai/mem0)

- **URL**: https://github.com/mem0ai/mem0
- **Stars**: ~25k+ (as of early 2026)
- **Status**: Actively maintained, backed by commercial entity (mem0.ai)
- **Language**: Python

### Architecture
- **Storage**: Hybrid — vector DB (Qdrant, Pinecone, ChromaDB) + graph DB (Neo4j) + key-value store
- **Memory Types**: User memories, session memories, agent memories; supports short-term and long-term
- **Retrieval**: Vector similarity search with LLM-based relevance scoring; supports memory consolidation via LLM summarization
- **Key Abstraction**: `Memory` class with `add()`, `search()`, `get_all()`, `delete()` APIs

### Key Features
- Self-improving memory — LLM decides what to remember, update, or forget
- Multi-level memory: user, session, agent scopes
- Graph memory for relational knowledge (Neo4j integration)
- Built-in conflict resolution when new memories contradict old ones
- REST API server mode for production deployment
- Integrations: OpenAI, LangChain, LlamaIndex, CrewAI, Autogen

### Design Decisions
- LLM-in-the-loop: Uses LLM to extract facts from conversations and decide memory operations
- Memory as structured facts, not raw conversation chunks
- Dual retrieval: vector similarity + graph traversal

### Strengths
- Simple API, easy to get started
- Production-ready with server mode
- Good ecosystem integrations

### Gaps
- Heavy dependency on LLM for all memory operations (cost, latency)
- Limited support for procedural memory (how-to knowledge)
- No built-in memory decay/forgetting mechanism beyond explicit deletion
- Graph memory is relatively new, less mature

---

## 2. Letta (formerly MemGPT) — letta-ai/letta

- **URL**: https://github.com/letta-ai/letta
- **Stars**: ~15k+
- **Status**: Actively maintained, commercial platform (letta.com)
- **Language**: Python

### Architecture
- **Concept**: OS-inspired memory hierarchy — "virtual context management"
- **Storage**: PostgreSQL (primary), with vector search via pgvector
- **Memory Types**:
  - **Core memory** (in-context): Persona + human blocks, always in LLM context window
  - **Archival memory** (out-of-context): Long-term storage with vector retrieval
  - **Recall memory**: Conversation history with search
- **Retrieval**: Agent actively manages own memory via function calls (self-editing memory)

### Key Features
- Agent-driven memory management — the agent decides when to read/write memory
- Stateful agents with persistent memory across sessions
- Memory tools as function calls: `core_memory_append`, `core_memory_replace`, `archival_memory_insert`, `archival_memory_search`
- Multi-agent support with shared memory blocks
- ADE (Agent Development Environment) — visual tool for building agents
- Letta Cloud for managed deployment

### Design Decisions
- **Self-editing memory**: Unlike Mem0's external memory layer, Letta gives the agent explicit control over its memory operations
- **OS metaphor**: Main context = RAM, archival = disk, recall = conversation log
- **Function-calling paradigm**: Memory operations are tools the agent invokes
- Core memory is always visible to the agent (like pinned context)

### Strengths
- Most sophisticated memory management model — agent has agency over its memory
- Strong theoretical foundation (MemGPT paper)
- Excellent for long-running, evolving agents
- Built-in memory benchmarks (MemBench)

### Gaps
- Higher complexity — steeper learning curve
- Requires more LLM calls (agent must decide memory operations each turn)
- PostgreSQL dependency may be heavy for simple use cases
- Less flexible storage backends compared to Mem0

---

## 3. Zep — getzep/zep + getzep/graphiti

- **URL**: https://github.com/getzep/zep (server) + https://github.com/getzep/graphiti (knowledge graph)
- **Stars**: ~3k+ (zep) + ~3k+ (graphiti)
- **Status**: Active, YC-backed startup
- **Language**: Python (graphiti), Go + Python (zep server)

### Architecture
- **Concept**: "Context engineering platform" — temporal knowledge graph for agent memory
- **Storage**: Neo4j (graph) + vector embeddings
- **Memory Types**:
  - **Episodic memory**: Conversation facts as timestamped graph nodes
  - **Semantic memory**: Entity knowledge extracted from conversations
  - **Community memory**: Aggregate knowledge across users
- **Retrieval**: Graph traversal + vector similarity, sub-200ms latency target

### Key Features
- **Graphiti**: Temporal knowledge graph engine — entities and relationships evolve over time
- Automated fact extraction from conversations
- Entity resolution and relationship tracking
- Bi-temporal data model (valid time + transaction time)
- Graph RAG for retrieval
- State-of-the-art memory benchmark results (per their paper)

### Design Decisions
- Graph-first approach — relationships are first-class citizens
- Temporal modeling — memories have time dimensions, enabling "what did I know at time T" queries
- Separation of concerns: Graphiti (graph engine) is independent from Zep (platform)

### Strengths
- Strongest relational/graph memory model
- Temporal awareness is unique differentiator
- Graphiti is usable standalone
- Published research paper on architecture

### Gaps
- Neo4j dependency (operational complexity)
- Zep Cloud is the primary product; open-source version is more limited
- Less focus on procedural memory
- Smaller community than Mem0/Letta

---

## 4. Cognee — topoteretes/cognee

- **URL**: https://github.com/topoteretes/cognee
- **Stars**: ~3k+
- **Status**: Active development
- **Language**: Python

### Architecture
- **Concept**: "Knowledge engine" — deterministic data ingestion pipeline for AI memory
- **Storage**: Pluggable — supports Qdrant, Weaviate, PGVector, Neo4j, FalkorDB, Milvus
- **Memory Types**: Knowledge graph nodes + vector embeddings
- **Retrieval**: Hybrid graph + vector search

### Key Features
- Multi-format data ingestion (PDF, audio, video, text, code)
- Automatic knowledge graph construction from unstructured data
- Deterministic pipelines (no LLM randomness in data processing)
- Modular pipeline architecture
- Also maintains [awesome-ai-memory](https://github.com/topoteretes/awesome-ai-memory) — curated list of memory tools

### Design Decisions
- Pipeline-oriented: Memory is built through explicit data processing steps
- Focus on data quality and determinism over LLM-driven extraction
- Multi-modal from the start

### Strengths
- Most flexible storage backend support
- Deterministic processing reduces hallucination risk
- Good for structured knowledge management
- Active in community building (awesome-ai-memory)

### Gaps
- Less focused on conversational memory specifically
- Newer project, API still evolving
- Less integrated with LLM agent frameworks
- More of a knowledge engine than an agent memory system

---

## 5. LangChain Memory

- **URL**: Part of https://github.com/langchain-ai/langchain
- **Stars**: ~100k+ (langchain monorepo)
- **Language**: Python, JavaScript/TypeScript

### Architecture
- **Concept**: Modular memory components within the LangChain agent framework
- **Memory Types**:
  - `ConversationBufferMemory` — raw conversation history
  - `ConversationSummaryMemory` — LLM-summarized history
  - `ConversationBufferWindowMemory` — sliding window
  - `ConversationKGMemory` — knowledge graph extraction
  - `VectorStoreRetrieverMemory` — vector similarity retrieval
  - `EntityMemory` — entity tracking across conversations

### Key Features
- Wide variety of memory types
- Easy to compose with chains and agents
- Any vector store as backend
- LangGraph integration for stateful agent workflows

### Design Decisions
- Memory as pluggable components in a pipeline
- Each memory type is a simple class with `load_memory_variables()` and `save_context()`
- Conversation-centric (input/output pairs)

### Strengths
- Largest ecosystem, most tutorials and examples
- Simple abstraction, easy to understand
- LangGraph provides more sophisticated state management

### Gaps
- Memory types are relatively shallow — no deep consolidation or reflection
- No built-in memory importance scoring or decay
- Primarily conversation-focused, weak on long-term semantic memory
- Memory modules are somewhat legacy (LangGraph is the recommended path now)

---

## 6. LlamaIndex Memory

- **URL**: Part of https://github.com/run-llama/llama_index
- **Stars**: ~40k+
- **Language**: Python

### Architecture
- **Concept**: Memory as indexed knowledge for retrieval
- **Key Components**:
  - `ChatMemoryBuffer` — conversation window management
  - `VectorMemory` — vector-indexed past interactions
  - Knowledge graph indices
  - Composable indices (tree, list, keyword, vector)

### Key Features
- Strong RAG integration — memory and retrieval are unified
- Index composability — combine multiple memory sources
- Property graph support for structured knowledge
- Workflow-based agent architecture with memory

### Strengths
- Best-in-class retrieval and indexing
- Flexible index composition
- Strong document/knowledge management

### Gaps
- Memory is secondary to retrieval (not the core focus)
- Less agent-centric memory management
- No self-improving or self-editing memory paradigm

---

## 7. Other Notable Projects

### MemoryScope
- Focus on LLM chatbot memory management
- Chinese-origin project, gaining traction
- Bilingual memory with consolidation

### Haystack (deepset)
- Pipeline-based RAG framework
- Memory through conversation stores and retrievers
- More RAG-focused than memory-focused

### CrewAI Memory
- Built-in memory for multi-agent crews
- Short-term, long-term, entity, and contextual memory
- Integrated with their agent framework

---

## Comparison Matrix

| Feature | Mem0 | Letta | Zep/Graphiti | Cognee | LangChain | LlamaIndex |
|---------|------|-------|-------------|--------|-----------|------------|
| **Stars** | ~25k | ~15k | ~6k | ~3k | ~100k | ~40k |
| **Architecture** | Hybrid (vector+graph) | OS-inspired hierarchy | Temporal KG | Pipeline+KG | Pluggable modules | Index-centric |
| **Storage Backends** | Many (Qdrant, Pinecone, Neo4j...) | PostgreSQL+pgvector | Neo4j | Many (Qdrant, Weaviate...) | Any vectorstore | Any index |
| **Self-managing Memory** | Yes (LLM extracts) | Yes (agent edits) | Yes (auto-extraction) | No (deterministic) | No | No |
| **Graph Support** | Yes (Neo4j) | Limited | Yes (core) | Yes | Limited | Yes |
| **Temporal Awareness** | No | Limited | Yes (core) | No | No | No |
| **Multi-agent** | Yes | Yes | Yes | Limited | Via LangGraph | Limited |
| **Memory Decay** | No | No | Implicit (temporal) | No | Window-based | No |
| **Standalone** | Yes | Yes (server) | Yes | Yes | Framework-bound | Framework-bound |
| **Production Ready** | Yes (cloud+OSS) | Yes (cloud+OSS) | Yes (cloud+OSS) | Growing | Yes | Yes |

---

## Gap Analysis — Opportunities for Hippocampus

1. **No project does neuroscience-inspired memory well**: Human memory has consolidation (hippocampus→cortex), decay, interference, emotional tagging — none of these projects model this deeply
2. **Procedural memory is universally weak**: How-to knowledge, learned skills, action patterns are underserved
3. **Memory lifecycle management**: No project has sophisticated forgetting/decay — memories accumulate indefinitely
4. **Cross-framework compatibility**: Most solutions are tied to specific frameworks or require their own server
5. **Memory evaluation**: No standardized benchmarks beyond Letta's MemBench
6. **Lightweight deployment**: Most solutions require external databases — there's room for an embedded/SQLite-first approach
7. **Multi-modal memory**: Remembering images, code snippets, structured data alongside text
