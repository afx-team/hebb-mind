---
description: "Migrate AI agent memory from mem0, Letta, or Zep to Hebb Mind: concept and API mapping, before/after code, data import, and an honest gap analysis."
---

# Migration from mem0 / Letta / Zep

This page maps the concepts and APIs of the three most-asked-about agent-memory frameworks onto Hebb Mind, plus shows how to move data over. Hebb Mind is younger than all three; we call out the gaps honestly so you can decide whether the move makes sense for your use case today.

All Python snippets use the public facade, which runs the engine **in-process** (its own storage, embedder, knowledge graph, and searcher — no HTTP server):

```python
from hebb import HebbMind

mem = HebbMind()  # resolves the workspace: $HEBB_HOME → nearest hebb.json → ~/.hebb
```

The facade signatures used below:

- `mem.add(content, *, partition="mem_hippocampus", importance=5.0, tags=None, metadata=None, source="library") -> Memory`
- `mem.search(query, *, top_k=10, partition_ids=None, tags=None, ...) -> list[MemorySearchResult]` — read content via `hit.memory.content`.

The facade has **no `ingest()` method** — calling one on the `mem` object raises `AttributeError`. For bulk/turn ingestion (LLM fact extraction over a chat turn), call the REST endpoint `POST /api/v1/ingest`, or loop `mem.add()` for verbatim per-turn storage. The REST endpoints below require the background service to be installed and running (`hebb service install`); the in-process facade does not. See [Quick Start](../quick-start.md).

---

## From mem0

[mem0ai/mem0](https://github.com/mem0ai/mem0) is the closest-shaped peer: REST-style add/search/update/delete API around a vector store with optional graph and LLM-driven fact extraction.

### Concept mapping

| mem0 | Hebb Mind | Notes |
|---|---|---|
| `Memory` | `Memory` | Same idea — a single piece of remembered text. |
| `user_id` / `agent_id` / `run_id` | `partition_id` | Hebb Mind uses one orthogonal namespace; combine your IDs with a separator (e.g. `f"{user}:{agent}"`). |
| `categories` (auto-extracted) | `tags` (extracted by consolidation) | Hebb Mind tags are extracted by the consolidation agent, not at write time. |
| `metadata` (free-form dict) | `metadata` (free-form dict) | One-to-one. |
| `add()` infers facts via LLM | `POST /api/v1/ingest` infers facts; `POST /api/v1/memories` stores verbatim | Two endpoints in Hebb Mind; pick `ingest` for the mem0-style "give me a turn, extract memories" behaviour. |
| Hosted "Mem0 Platform" | None — local-only today | See [FAQ](../faq.md#is-there-a-hosted-version). |
| Graph memory (Neo4j optional) | Built-in tag/co-occurrence knowledge graph | Different model. mem0's graph is entity-relation; ours is tag-edge. See [Knowledge Graph](../concepts/knowledge-graph.md). |

### Code: before / after

**Before (mem0):**

```python
from mem0 import Memory

m = Memory()
m.add("I'm allergic to peanuts", user_id="alice", metadata={"source": "chat"})
results = m.search("food allergies", user_id="alice", limit=5)
```

**After (Hebb Mind):**

```python
from hebb import HebbMind

mem = HebbMind()
mem.add(
    "I'm allergic to peanuts",
    partition="alice",
    metadata={"source": "chat"},
)
results = mem.search("food allergies", partition_ids=["alice"], top_k=5)
for hit in results:
    print(hit.score, hit.memory.content)
```

### Data import

We do not yet ship a one-shot importer for mem0 dumps. The schemas are similar enough that a ~30-line script that reads mem0's `get_all()` and calls `mem.add()` per row will move most data; we're tracking a first-class importer in [issue #TBD](https://github.com/afx-team/hebb-mind/issues). PRs welcome.

```python
from hebb import HebbMind

mem = HebbMind()
for row in m.get_all(user_id="alice")["results"]:   # mem0 export
    mem.add(row["memory"], partition="alice", metadata=row.get("metadata"))
```

### Where we lag mem0 today

- No managed/hosted offering — you run the binary.
- No first-party Neo4j graph backend (we have a built-in tag graph; richer entity-relation extraction is on the roadmap).
- mem0 has more SDK surface area (TypeScript, more integrations). We have Python + REST + MCP.

---

## From Letta

[letta-ai/letta](https://github.com/letta-ai/letta) (formerly MemGPT) is a stateful agent framework with a memory layer, not a memory-only framework. The migration question is: "Can I use Hebb Mind as Letta's memory while keeping my agent loop?" Mostly yes.

### Concept mapping

| Letta | Hebb Mind | Notes |
|---|---|---|
| Agent (with persisted state) | n/a — bring your own agent loop | Hebb Mind stores memories; it does not run an agent. |
| Core memory (in-context blocks) | n/a | Keep using Letta blocks; pull additions from Hebb Mind on each turn. |
| Recall memory (full conversation history) | `POST /api/v1/ingest` per turn | Replace Letta's recall storage with Hebb Mind ingestion. |
| Archival memory (vector store) | `HebbMind.add` + `HebbMind.search` | Direct replacement. |
| `archival_memory_search(query)` tool | Wrap `mem.search(query=...)` and expose it as your tool | One-line shim. |
| Sources / data ingestion | `POST /api/v1/memories` (batch) or `ingest` for chats | — |

### Code: before / after

**Before (Letta archival memory tool):**

```python
# Inside a Letta agent
agent.memory.archival_memory_insert("User prefers dark mode")
hits = agent.memory.archival_memory_search("UI preferences", count=5)
```

**After (Hebb Mind, used as Letta's archival store):**

```python
from hebb import HebbMind

mem = HebbMind()
mem.add("User prefers dark mode", partition=agent_id, importance=7.5)
hits = mem.search("UI preferences", partition_ids=[agent_id], top_k=5)
```

Register that as a Letta tool and the rest of the agent loop is unchanged.

### Data import

Letta stores archival memory in PostgreSQL (or SQLite). The simplest path is a SELECT against Letta's `archival_passage` table followed by `mem.add()` per row in a small script. No first-party importer yet — see [issue #TBD](https://github.com/afx-team/hebb-mind/issues).

### Where we lag Letta today

- No agent runtime, no tool-calling loop, no model abstraction. Hebb Mind is the storage half only.
- No core/recall/archival hierarchy with automatic eviction policies — we have a single store with consolidation/forgetting on top.
- No multi-agent orchestration primitives.

If you want a full agent framework with built-in memory, stay on Letta and treat Hebb Mind as a swap-in archival backend.

---

## From Zep

[getzep/zep](https://github.com/getzep/zep) (and the open-source [graphiti](https://github.com/getzep/graphiti)) lead with knowledge-graph reasoning over chat history. Zep Cloud adds session-scoped memory and search.

### Concept mapping

| Zep | Hebb Mind | Notes |
|---|---|---|
| `Session` | `partition_id` | Use the Zep session id as the partition. |
| `Message` | A `Memory` ingested via `/ingest` | Zep stores raw messages and synthesized facts; Hebb Mind does both via `ingest`. |
| `Fact` (synthesized via LLM) | `Memory` written by the consolidation agent | Comparable concept; ours is consolidated periodically rather than on every message. |
| Graphiti knowledge graph (entity + temporal edges) | Tag/co-occurrence graph | **Zep's graph is richer.** See gaps below. |
| `memory.search()` | `HebbMind.search()` | API is similar. |
| Zep Cloud / hosted | None | Local-only. |

### Code: before / after

**Before (Zep Python SDK):**

```python
from zep_python import ZepClient
from zep_python.memory import Memory, Message

zep = ZepClient(base_url="https://api.getzep.com", api_key="...")
zep.memory.add_memory(
    session_id="alice",
    memory=Memory(messages=[Message(role="user", content="I run a vegan bakery")]),
)
results = zep.memory.search_memory("alice", text="user occupation", limit=5)
```

**After (Hebb Mind):**

```python
from hebb import HebbMind

mem = HebbMind()
# Verbatim per-turn storage via the in-process facade:
mem.add("I run a vegan bakery", partition="alice", source="chat")
results = mem.search("user occupation", partition_ids=["alice"], top_k=5)
```

To get Zep-style LLM **fact extraction** over a raw turn (instead of verbatim storage), POST the turn to the running service's ingest endpoint:

```bash
curl -X POST http://localhost:8321/api/v1/ingest \
  -H 'Content-Type: application/json' \
  -d '{"content": "user: I run a vegan bakery", "partition_id": "alice"}'
```

### Data import

Zep exposes `GET /sessions/{id}/messages` and `GET /sessions/{id}/facts`. A small loop that pulls those and calls `mem.add()` per item covers the common case; for raw messages you want fact-extracted, POST each to `/api/v1/ingest` instead. No first-party importer yet — [issue #TBD](https://github.com/afx-team/hebb-mind/issues).

### Where we lag Zep today

- **Graph reasoning.** Graphiti models entities and *temporally-scoped* relations between them ("Alice worked-at Bakery from 2022-01 to 2024-07"). Our graph is tag-edge with frequency weights — strong for recall, weaker for explicit temporal-relational queries.
- **Fact synthesis cadence.** Zep extracts facts on every message; we extract during scheduled consolidation. Fresher facts in Zep, lower LLM cost in Hebb Mind.
- **Hosted offering and SLAs.** Zep has them, we don't.

If your use case leans on entity-temporal graph queries today, Zep / Graphiti is still the more capable choice. If you want local-first, single-binary, MCP-native memory with neuroscience-flavoured forgetting, Hebb Mind is the closer fit.

---

## Common to all three migrations

- **Test in a fresh partition first.** Migrate one user/agent/session before bulk-importing.
- **Re-consolidate after import.** `curl -X POST http://localhost:8321/api/v1/admin/consolidate` runs the consolidation agent over the new memories — required for tag extraction and dedup. Needs `llm_model` set (and `llm_api_key` for hosted providers); see [Troubleshooting](../troubleshooting.md#consolidate-returns-processed-0-or-no-conflicts-get-resolved).
- **Verify with the Web Console.** Open <http://localhost:8321/> and skim the Memories tab to confirm the import landed where you expected. See [Web Console](./web-console.md).
- **Pick the right embedding dimension up front.** Switching `embedding_model` after ingest forces a re-embed (`hebb memory reembed`). The default `all-MiniLM-L6-v2` (384-d) is a fast English starting point; for the strongest English retrieval, `hebb setup --profile best` selects `BAAI/bge-large-en-v1.5` (1024-d). See [Switch the Embedding Model](./switch-embedding-model.md).
