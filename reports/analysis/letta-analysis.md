# Letta (formerly MemGPT) - Feature Analysis

**Repository**: https://github.com/letta-ai/letta
**Version analyzed**: 0.16.7 (commit from April 2026)
**Date**: 2026-04-20
**Analyst**: Code Analyst Agent

---

## Overview

Letta is an open-source agent memory framework descended from the MemGPT research project. It provides stateful, memory-persistent AI agents with a three-tier memory architecture (core, archival, recall) and a full-featured REST API server. The project has matured significantly from its academic origins into a production-grade platform with hosted cloud services.

### Memory Architecture

Letta implements a three-tier memory model:

1. **Core Memory** -- In-context blocks that live inside the LLM prompt window. These are editable by the agent via tool calls (`memory_replace`, `memory_insert`, `memory_rethink`, `memory_apply_patch`). Each block has a label, character limit, and description. Supported out of the box: `human`, `persona`, plus arbitrary user-created blocks.

2. **Archival Memory** -- Persistent, vector-searchable long-term storage. Implemented as `ArchivalPassage` records with embeddings. Search uses semantic similarity (cosine distance). Supports tags for filtering. Stored in PostgreSQL (with pgvector) or SQLite (with sqlite-vec), or optionally in Turbopuffer/Pinecone.

3. **Recall Memory** -- Historical conversation messages. Searchable via hybrid search (text + semantic). Messages are stored in the database and can be recalled with date-range and role filters.

---

## Feature Verification

### 1. Memory Consolidation -- PARTIAL SUPPORT

Letta has **two consolidation-adjacent mechanisms** but neither is a true automatic memory consolidation system.

#### a) Sleeptime Agent (Background Memory Reorganization)

Letta introduces a **"sleeptime agent"** -- a separate background agent that asynchronously reviews conversations after they occur and updates memory blocks. Key details:

- Defined in `letta/groups/sleeptime_multi_agent_v4.py`
- When the primary agent responds to a user, the sleeptime agent is triggered in the background
- The sleeptime agent receives the primary agent's response messages with a system reminder: *"You are a sleeptime agent... Your primary role is memory management. Review the conversation and use your memory tools to update any relevant memory blocks."*
- Runs on a configurable frequency (`sleeptime_agent_frequency` -- every N turns)
- Can use `rethink_user_memory`, `finish_rethinking_memory`, and `store_memories` tools
- This is LLM-driven consolidation, not algorithmic -- the LLM decides what to reorganize

**This is the closest thing to consolidation in Letta**, but it is:
- Optional and must be explicitly enabled (`enable_sleeptime=True`)
- Entirely LLM-driven (no deterministic or rule-based merging)
- Only operates on core memory blocks (in-context), not archival passages
- Does not merge or deduplicate archival memories

#### b) Context Window Compaction (Message Summarization)

When the context window fills up, Letta **compacts the conversation history** through summarization. This is implemented in `letta/services/summarizer/`. Four compaction modes exist:

- `static_message_buffer` -- Keeps only the N most recent messages
- `partial_evict_message_buffer` -- Evicts a percentage of older messages, replaces with an LLM-generated summary
- `sliding_window` -- Sliding window summarization using a separate LLM call
- `self_compact_all` / `self_compact_sliding_window` -- The agent's own LLM generates the summary (Claude Code-style)

**This is conversation summarization, not memory consolidation.** It compresses the dialogue history but does not merge, deduplicate, or reorganize stored memories.

#### c) `memory_rethink` Tool

The `memory_rethink` function allows the agent to completely rewrite a memory block: *"Use this tool to make large sweeping changes (e.g. when you want to condense or reorganize the memory blocks)."* This is agent-initiated manual consolidation, not automatic.

#### Summary

Letta does NOT have automatic memory consolidation that merges, compresses, or reorganizes stored archival memories over time. The sleeptime agent is the closest mechanism, but it operates on core memory blocks only and relies entirely on LLM judgment. There is no system that automatically detects redundant archival passages and merges them, no periodic re-indexing of archival memory, and no importance-weighted reorganization.

---

### 2. Forgetting / Decay -- NOT SUPPORTED

Letta has **no memory decay or forgetting mechanism**.

- Archival memories (passages) have no `last_accessed_at`, `importance_score`, `decay_factor`, or `expiration_date` fields
- The `Passage` schema (`letta/schemas/passage.py`) has only: `id`, `text`, `embedding`, `embedding_config`, `created_at`, `is_deleted`, `tags`, `metadata`
- `is_deleted` is a boolean flag for manual deletion, not time-based decay
- There is no background process that prunes or deprecates old memories
- Archival memories can be explicitly deleted via API (`DELETE /agents/{agent_id}/archival-memory/{memory_id}`), but this is entirely manual
- The `FileBlock` schema has `last_accessed_at`, but this is only for file blocks (attached sources), not archival memories, and it tracks access time for the file open/close mechanism, not for decay

**Bottom line**: Once a memory is written to archival storage, it persists indefinitely unless explicitly deleted. There is no automatic forgetting based on time, access frequency, or relevance decay.

---

### 3. Knowledge Graph -- NOT SUPPORTED

Letta has **no built-in knowledge graph support**.

- No graph database integration (no Neo4j, NetworkX, or similar)
- No entity extraction or relationship modeling
- The `identity` schema (`letta/schemas/identity.py`) provides person-like identity tracking, but this is flat data, not a graph
- The git-backed memory system (`git_enabled` flag on agents) organizes memory blocks in a filesystem-like hierarchy (`system/persona`, `system/human`, `skills/*`), but this is a tree structure rendered as XML tags, not a semantic knowledge graph
- Archival memory search is purely vector-based (semantic similarity via embeddings)
- The `letta/schemas/enums.py` `VectorDBProvider` enum lists: `NATIVE` (pgvector/sqlite-vec), `TPUF` (Turbopuffer), `PINECONE` -- all vector stores, no graph stores

**Bottom line**: Letta's memory model is flat -- blocks and passages with vector search. There is no entity-relationship modeling, no graph traversal, and no structured knowledge representation.

---

### 4. Zero-Config Deploy -- PARTIAL SUPPORT

Letta supports SQLite as a fallback database when no PostgreSQL connection is configured, but **true zero-config is not achieved** because an LLM API key is still required.

#### Database Fallback

The `settings.py` contains a `DatabaseChoice` enum (`POSTGRES`, `SQLITE`) and this logic:

```python
@property
def database_engine(self) -> DatabaseChoice:
    return DatabaseChoice.POSTGRES if self.letta_pg_uri_no_default else DatabaseChoice.SQLITE
```

When no `LETTA_PG_URI` is set and no PostgreSQL credentials are provided, Letta falls back to SQLite. The `sqlite_functions.py` module registers `sqlite-vec` for vector similarity search, and the ORM models conditionally use `CommonVector` instead of pgvector's `Vector` type when on SQLite.

The `db.py` module, however, is **hardcoded to use PostgreSQL** (it creates an async engine with `asyncpg` driver). This means the server mode requires PostgreSQL, while the client/CLI mode can work with SQLite.

#### What Still Requires Configuration

- **LLM API key**: You must provide at least one LLM provider API key (OpenAI, Anthropic, etc.) for the agent to function. There is no bundled local model.
- **Embedding endpoint**: Archival memory search requires embeddings, which need an OpenAI API key or equivalent.
- **Server mode**: The REST API server (`letta server`) is hardcoded to PostgreSQL via `letta/server/db.py`.

**Bottom line**: The Letta CLI/client can fall back to SQLite for storage without configuration, but you must always configure an LLM provider. The server requires PostgreSQL. This is not "zero-config deploy" in the sense of running a fully functional local system without any external dependencies.

---

### 5. Multi-Model Support -- EXTENSIVE SUPPORT

Letta supports a wide range of LLM providers. The `ProviderType` enum in `letta/schemas/enums.py` lists 22 provider types:

| Provider | Client File |
|----------|------------|
| OpenAI | `openai_client.py` |
| Anthropic | `anthropic_client.py` |
| Azure OpenAI | `azure_client.py` |
| Google AI (Gemini) | `google_ai_client.py` |
| Google Vertex AI | `google_vertex_client.py` |
| AWS Bedrock | `bedrock_client.py` |
| Ollama | Uses OpenAI-compatible endpoint |
| vLLM | Uses OpenAI-compatible endpoint |
| SGLang | `sglang_native_client.py` |
| LM Studio | Uses OpenAI-compatible endpoint |
| Groq | `groq_client.py` |
| Together | `together_client.py` |
| Fireworks | `fireworks_client.py` |
| DeepSeek | `deepseek_client.py` |
| xAI (Grok) | `xai_client.py` |
| Mistral | `mistral.py` |
| MiniMax | `minimax_client.py` |
| OpenRouter | Uses OpenAI-compatible endpoint |
| Baseten | `baseten_client.py` |
| ZAI (ZhipuAI) | `zai_client.py` |
| ChatGPT OAuth | `chatgpt_oauth_client.py` |
| Hugging Face | Listed in enum, endpoint-based |

Each provider has dedicated API key configuration in `settings.py` and/or `conf.yaml`. The README states: *"Letta is fully model-agnostic"*.

**Bottom line**: Letta has excellent multi-model support with 22 provider types, covering all major commercial providers and popular self-hosted options (Ollama, vLLM, SGLang).

---

### 6. Web Management UI -- EXTERNAL / HOSTED ONLY

Letta's **open-source repository does not include a web management UI**.

- The `static_files.py` module only redirects `/` to `/docs` (Swagger API docs)
- The `compose.yaml` includes an nginx service, but it proxies to the REST API, not a management dashboard
- The `cors_origins` list includes `http://localhost:8283`, `http://localhost:8083`, and `http://localhost:3000`, suggesting a separate frontend may connect to the API server
- There is no React, Vue, or other frontend code in the repository

**Letta provides a hosted web UI at `app.letta.com`** (the "Letta Desktop" or "Memory Palace"), but this is a proprietary cloud service, not part of the open-source project.

**An open-source demo UI exists** at `github.com/letta-ai/letta-oss-ui` -- a fork of Claude-Cowork that provides a visual interface for running Letta Code agents. This is a separate repository, not bundled with the main Letta project.

**Bottom line**: No built-in web management UI in the open-source repo. The hosted UI at `app.letta.com` is a cloud service. The `letta-oss-ui` project provides a community-built alternative.

---

## Architecture Summary

```
+-------------------+     +------------------+     +--------------------+
|   Core Memory     |     |  Archival Memory |     |   Recall Memory    |
|   (in-context)    |     |  (vector store)  |     |   (messages)       |
|                   |     |                  |     |                    |
|  Block: human     |     |  ArchivalPassage |     |  Message[]         |
|  Block: persona   |     |  + embedding     |     |  + embeddings     |
|  Block: custom    |     |  + tags          |     |  + date filters   |
|                   |     |  + metadata      |     |                    |
|  Tools:           |     |                  |     |  Search:           |
|  - memory_replace |     |  Search:         |     |  - conversation_   |
|  - memory_insert  |     |  - archival_     |     |    search          |
|  - memory_rethink |     |    memory_search |     |                    |
|  - memory_apply   |     |  Insert:         |     |                    |
|    _patch         |     |  - archival_     |     |                    |
|                   |     |    memory_insert |     |                    |
+-------------------+     +------------------+     +--------------------+
        |                         |                         |
        +---------------------------------------------------------+
                                  |
                    +-------------v-------------+
                    |    Sleeptime Agent        |
                    |  (background, LLM-driven) |
                    |  Reviews conversations    |
                    |  Updates core memory      |
                    +---------------------------+
```

---

## Strengths

1. **Mature three-tier memory model** -- Core, archival, and recall are well-differentiated with clear APIs
2. **Excellent multi-model support** -- 22 LLM providers out of the box
3. **Sleeptime agent concept** -- Novel approach to background memory management
4. **Multiple compaction strategies** -- Four summarization modes with fallback chains
5. **Git-backed memory** -- Optional filesystem-like memory organization with versioning
6. **Production-grade server** -- FastAPI REST API with streaming, WebSocket support, Redis queues

## Weaknesses

1. **No memory consolidation** -- Archival memories are never automatically merged or reorganized
2. **No forgetting/decay** -- Memories persist indefinitely with no time-based or relevance-based pruning
3. **No knowledge graph** -- Flat vector-search model with no entity-relationship modeling
4. **SQLite support is incomplete** -- Server mode hardcodes PostgreSQL; SQLite only works for client mode
5. **LLM-dependent compaction** -- Memory summarization and sleeptime consolidation depend entirely on LLM quality and cost
6. **No local model fallback** -- Cannot run fully locally without external API keys

---

## Implications for Hippocampus

1. **Consolidation gap is a design opportunity** -- Letta's archival memory grows monotonically. A system that automatically detects redundant passages and merges them (importance-weighted, recency-aware) would be a meaningful differentiator. Consider: periodic background jobs that cluster similar passages and produce condensed summaries.

2. **Decay/forgetting is unexplored territory** -- None of the major open-source memory frameworks implement forgetting. Hippocampus could implement time-decayed relevance scoring, combining recency, access frequency, and importance -- analogous to human memory consolidation where unused memories fade.

3. **Knowledge graph as a complement** -- Letta's flat vector search is sufficient for simple retrieval but cannot capture relational knowledge (e.g., "Alice works for Company X, which is headquartered in City Y"). A lightweight knowledge graph layer could provide structured reasoning that vector search cannot.

4. **SQLite-first is viable** -- Letta's SQLite support is incomplete because their server was designed for cloud deployment. Hippocampus, targeting local/self-hosted use, could make SQLite the primary storage backend with zero external dependencies (embedding model being the remaining blocker).

5. **Sleeptime agent pattern is valuable** -- The concept of a background agent that asynchronously reorganizes memory after conversations is sound and aligns with hippocampal memory consolidation in neuroscience. However, it should be supplemented with deterministic, non-LLM consolidation steps (deduplication, importance scoring, decay) to reduce LLM cost and improve reliability.

6. **Simplicity wins** -- Letta's memory tool APIs (`memory_replace`, `memory_insert`, `archival_memory_search`) are well-designed and simple. Hippocampus should similarly prioritize developer experience with clean, composable primitives.