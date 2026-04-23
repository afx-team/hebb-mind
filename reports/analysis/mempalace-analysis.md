# MemPalace Technical Analysis

## Overview

MemPalace is a local-first AI memory system that stores conversation history and project files as verbatim text and retrieves them via semantic search. It targets developers and AI power users who want persistent memory across LLM sessions without sending data to the cloud.

**Repository**: https://github.com/MemPalace/mempalace
**Version**: 3.3.0 (as of analysis date)
**License**: MIT
**Language**: Python 3.9+
**Dependencies**: chromadb (>=1.5.4), pyyaml (>=6.0)
**Author**: milla-jovovich (Igor Lins e Silva), with ~10 contributors
**Codebase size**: ~15,670 lines of Python (core), ~15,014 lines of tests (53 test files)
**Maturity**: Beta (PyPI classifiers say "Development Status :: 4 - Beta"), but actively developed with 521 commits since Jan 2025, 5 tagged releases (v3.1.0 through v3.3.2)

The project positions itself as a "verbatim always" memory system, distinguishing from competitors like Mem0 that use LLM extraction. The core thesis is that raw text with good embeddings (ChromaDB's default sentence-transformers) beats LLM-extracted summaries because it preserves context. They report 96.6% R@5 on LongMemEval with zero API calls.

---

## Architecture

### Spatial Metaphor

MemPalace organizes memory using a physical-space metaphor inspired by the Method of Loci and Zettelkasten:

```
Palace (root data directory, ~/.mempalace/palace)
  Wing (broad category: person, project, topic)
    Room (time-based or topic-based grouping: day, session, subtopic)
      Drawer (verbatim text chunk, ~800 chars)
    Hall (cross-cutting categorization: emotional, technical, family)
  Closet (compressed index layer pointing to drawers, AAAK format)
  Tunnel (cross-wing link between related rooms)
```

### Core Module Structure

The system is organized into these functional areas:

**Ingest pipeline**: `miner.py`, `convo_miner.py`, `sweeper.py`, `normalize.py`, `general_extractor.py`
**Storage**: `backends/base.py`, `backends/chroma.py`, `palace.py`
**Retrieval**: `searcher.py`, `layers.py`
**Knowledge graph**: `knowledge_graph.py`
**Navigation**: `palace_graph.py`
**Indexing**: `dialect.py` (AAAK compression), `closet_llm.py` (optional LLM closets)
**Entity detection**: `entity_detector.py`, `entity_registry.py`
**Maintenance**: `dedup.py`, `repair.py`, `sweeper.py`, `migrate.py`
**Integration**: `mcp_server.py` (29 MCP tools), `cli.py`, `hooks_cli.py`
**Configuration**: `config.py`, `onboarding.py`
**i18n**: `i18n/` directory with 14 language JSON files

### Data Flow

```
Source Files/Conversations
    |
    v
[Normalize] -- detect format (Claude Code JSONL, ChatGPT JSON, Slack, plain text)
    |          strip noise tags, system chrome
    v
[Route] -- detect_room() for files, detect_convo_room() for conversations
    |      detect_hall() for cross-cutting categorization
    v
[Chunk] -- chunk_text() at 800 chars with 100-char overlap, paragraph-aware
    |      OR chunk_exchanges() for Q+A pair chunking in conversations
    v
[File to Palace] -- add_drawer() upserts to ChromaDB with metadata
    |               (wing, room, hall, source_file, chunk_index, entities, filed_at)
    |
    v
[Build Closets] -- build_closet_lines() extracts topics, entities, quotes
                   upsert to mempalace_closets collection as compressed pointers
```

---

## Memory Model

### Memory Types

MemPalace does NOT use the classical episodic/semantic/procedural taxonomy. Instead, it categorizes by content type:

1. **Verbatim drawers** -- The primary storage. Every piece of text is stored exactly as written, chunked at ~800 characters. This is the fundamental design principle: "Never summarize, paraphrase, or lossy-compress user data."

2. **Closets** -- Compressed index layer. Each closet contains pipe-separated pointer lines of the form `topic|entities|->drawer_id_a,drawer_id_b`. Built via regex extraction from drawer content. Limited to ~1500 chars per closet.

3. **Knowledge graph triples** -- Entity-relationship facts with temporal validity windows. Stored in SQLite, not ChromaDB. Format: `subject -> predicate -> object` with `valid_from` and `valid_to` dates.

4. **Agent diaries** -- Per-agent journal entries stored as drawers in a dedicated wing (e.g., `wing_lumi/diary`). Written in AAAK compressed format.

5. **General extraction types** (via `general_extractor.py`): decisions, preferences, milestones, problems, emotional moments. Classified by regex-based keyword scoring, no LLM required.

### Memory Representation

Each drawer in ChromaDB has:

- **Document**: Verbatim text content (~800 chars)
- **ID**: Deterministic hash: `drawer_{wing}_{room}_{sha256(source_file + chunk_index)[:24]}`
- **Metadata**:
  - `wing` (str): Project/person/topic category
  - `room` (str): Subtopic within wing
  - `hall` (str): Cross-cutting type (emotional, technical, family, etc.)
  - `source_file` (str): Origin file path
  - `chunk_index` (int): Position within source file
  - `filed_at` (str): ISO timestamp
  - `normalize_version` (int): Schema version for rebuild detection
  - `source_mtime` (float): File modification time for change detection
  - `entities` (str): Semicolon-separated entity names
  - `added_by` (str): Agent or tool that filed this
  - `ingest_mode` (str): "convos", "sweep", "registry"

### Memory Lifecycle

**Creation**: Content enters via `miner.py` (project files), `convo_miner.py` (conversations), `sweeper.py` (message-granular Claude Code JSONL), or `mcp_server.py` (direct `mempalace_add_drawer` calls).

**Consolidation**: There is no consolidation or compression of stored content. The AAAK dialect (`dialect.py`) produces lossy summaries for the closet index layer, but the original drawers remain untouched. The `Dialect.compress()` method extracts entities, topics, key sentences, emotions, and flags into a compact format -- but this is only for the index, never a replacement for the original.

**Forgetting/Decay**: There is NO automatic forgetting, decay, or garbage collection. The `dedup.py` module can remove near-duplicate drawers (cosine distance < 0.15 threshold), and `sweeper.py` provides idempotent re-ingestion, but nothing ages out old memories. The knowledge graph supports `invalidate()` to mark facts as expired (setting `valid_to`), but expired triples remain in the database.

**Retrieval**: Multi-stage hybrid search (see Retrieval section below).

---

## Technical Implementation Details

### Retrieval Algorithms

The search pipeline in `searcher.py` implements a multi-stage hybrid approach:

**Stage 1 -- Vector retrieval (floor)**:
Query ChromaDB's `mempalace_drawers` collection with the search query. Over-fetches 3x the requested results for re-ranking. ChromaDB uses cosine distance with HNSW index. The default embedding model is ChromaDB's built-in sentence-transformers (all-MiniLM-L6-v2 by default, ~300 MB).

**Stage 2 -- Closet boosting (signal, not gate)**:
Query `mempalace_closets` collection in parallel. Closet hits produce a rank-based distance boost for matching drawers. The boost values are: `[0.40, 0.25, 0.15, 0.08, 0.04]` for ranks 0-4. Closets with cosine distance > 1.5 are ignored. This is designed so weak closets (from regex extraction on narrative content) can only help, never hurt.

**Stage 3 -- Drawer-grep enrichment**:
For closet-boosted hits, the system fetches ALL drawers from the matching source file, then uses keyword overlap (`_tokenize(query)` intersection) to find the best chunk within that source. It then returns that chunk plus its immediate neighbors (chunks at index-1 and index+1), providing context continuity.

**Stage 4 -- BM25 hybrid re-ranking**:
The final candidate set is re-ranked using a convex combination:
```
score = 0.6 * vector_similarity + 0.4 * normalized_bm25
```
Where BM25 is computed with Okapi-BM25 (k1=1.5, b=0.75) using Lucene-style IDF smoothing. BM25 scores are min-max normalized within the candidate set.

**Stage 5 -- Optional LLM rerank** (benchmark path only):
For the 99%+ benchmark results, an LLM (Haiku, Sonnet, or local model) reranks the top-20 candidates. This is NOT part of the default search path.

### Memory Stack (layers.py)

A 4-layer context management system:

- **Layer 0 -- Identity** (~100 tokens): Static file at `~/.mempalace/identity.txt`. Always loaded into context.
- **Layer 1 -- Essential Story** (~500-800 tokens): Auto-generated from top drawers sorted by importance metadata. Grouped by room, truncated to 3200 chars. Scans up to 2000 drawers at most 15 moments.
- **Layer 2 -- On-Demand** (~200-500 tokens each): Wing/room-filtered retrieval, triggered when a specific topic arises.
- **Layer 3 -- Deep Search** (unlimited): Full semantic search via ChromaDB.

The `MemoryStack` class provides the unified interface:
```python
stack = MemoryStack()
stack.wake_up()       # L0 + L1, ~600-900 tokens
stack.recall(wing=..) # L2
stack.search(query)   # L3
```

### Chunking Strategy

Two chunking approaches:

**File chunking** (`miner.chunk_text()`):
- Fixed window of 800 chars with 100-char overlap
- Boundary-aware: prefers to break at paragraph boundaries (`\n\n`), falls back to line boundaries (`\n`), then hard split
- Minimum chunk size: 50 chars

**Conversation chunking** (`convo_miner.chunk_exchanges()`):
- Exchange-pair based: one user turn (`>` marker) + AI response = one unit
- If the combined exchange exceeds 800 chars, it is split into continuation drawers
- Fallback to paragraph chunking if fewer than 3 `>` markers detected

### Knowledge Graph

Implemented in `knowledge_graph.py` using SQLite with WAL mode.

**Schema**:
```sql
entities (id TEXT PK, name TEXT, type TEXT, properties TEXT JSON, created_at TEXT)
triples  (id TEXT PK, subject TEXT FK, predicate TEXT, object TEXT FK,
          valid_from TEXT, valid_to TEXT, confidence REAL DEFAULT 1.0,
          source_closet TEXT, source_file TEXT, source_drawer_id TEXT,
          adapter_name TEXT, extracted_at TEXT)
```

**Key operations**:
- `add_triple(subject, predicate, obj, valid_from=..., valid_to=...)` -- Auto-creates entities. Deduplicates: returns existing triple ID if subject+predicate+object match and `valid_to IS NULL`.
- `invalidate(subject, predicate, obj, ended=...)` -- Sets `valid_to` on matching triples.
- `query_entity(name, as_of=..., direction="outgoing"|"incoming"|"both")` -- Retrieves all relationships for an entity, optionally filtered to a point in time.
- `timeline(entity_name=None)` -- Chronological list of facts, limited to 100.

Entity IDs are derived deterministically: `name.lower().replace(" ", "_").replace("'", "")`.

Thread safety is ensured via `threading.Lock()` on all operations.

### AAAK Dialect (dialect.py)

A lossy summarization format for the closet/index layer. NOT a compression algorithm -- the original text cannot be reconstructed.

**Format**:
```
Header:   FILE_NUM|PRIMARY_ENTITY|DATE|TITLE
Zettel:   ZID:ENTITIES|topic_keywords|"key_quote"|WEIGHT|EMOTIONS|FLAGS
Tunnel:   T:ZID<->ZID|label
Arc:      ARC:emotion->emotion->emotion
```

**Encoding rules**:
- Entities: 3-letter uppercase codes (e.g., "ALC" for Alice)
- Emotions: Compact codes (e.g., "vul" for vulnerability, "joy" for joy)
- Flags: ORIGIN, CORE, SENSITIVE, PIVOT, GENESIS, DECISION, TECHNICAL

The `Dialect.compress(text)` method extracts:
1. Entities (from known entity map or auto-coded first 3 chars)
2. Topics (frequency-ranked content words after stopword removal)
3. Key sentence (scored by decision words, length preference)
4. Emotions (keyword signals like "decided"->determ, "worried"->anx)
5. Flags (keyword signals like "decided"->DECISION, "architecture"->TECHNICAL)

### Storage Backend

**Current**: ChromaDB (local PersistentClient, cosine HNSW space)

**Backend abstraction** (`backends/base.py`):

```python
class BaseCollection(ABC):
    def add(*, documents, ids, metadatas=None, embeddings=None) -> None
    def upsert(*, documents, ids, metadatas=None, embeddings=None) -> None
    def query(*, query_texts=None, query_embeddings=None, n_results=10,
              where=None, include=None) -> QueryResult
    def get(*, ids=None, where=None, limit=None, offset=None, include=None) -> GetResult
    def delete(*, ids=None, where=None) -> None
    def count() -> int

class BaseBackend(ABC):
    def get_collection(*, palace: PalaceRef, collection_name, create=False) -> BaseCollection
```

Typed result dataclasses: `QueryResult`, `GetResult` with backward-compatible dict access via `_DictCompatMixin`.

**Planned backends** (per ROADMAP.md): PostgreSQL with pg_sorted_heap, LanceDB for multi-device sync, PalaceStore (custom).

**ChromaDB specifics** (`backends/chroma.py`):
- `ChromaBackend` caches `PersistentClient` instances per palace path
- Freshness check via inode + mtime of `chroma.sqlite3` -- detects palace rebuilds
- `quarantine_stale_hnsw()` -- Renames HNSW segment dirs that are >1h stale vs SQLite, preventing segfaults
- `_fix_blob_seq_ids()` -- Fixes ChromaDB 0.6->1.5 migration bug (BLOB seq_id -> INTEGER)
- Where-clause validation: raises `UnsupportedFilterError` for unknown operators (no silent dropping)

### Source Adapter Plugin System (RFC 002)

A plugin architecture for ingest sources, defined in `sources/base.py`:

```python
class BaseSourceAdapter(ABC):
    name: ClassVar[str]
    def ingest(*, source: SourceRef, palace: PalaceContext) -> Iterator[DrawerRecord]
    def describe_schema() -> AdapterSchema
    def is_current(*, item, existing_metadata) -> bool
```

Entry point group: `mempalace.sources`. No first-party adapters registered yet -- `miner.py` and `convo_miner.py` are slated for migration in a follow-up.

### MCP Integration

`mcp_server.py` implements a JSON-RPC MCP server with 29 tools across these categories:

**Read tools** (10): status, list_wings, list_rooms, get_taxonomy, search, check_duplicate, get_aaak_spec, traverse, find_tunnels, graph_stats
**Write tools** (6): add_drawer, delete_drawer, get_drawer, list_drawers, update_drawer, diary_write/read
**Knowledge graph** (5): kg_query, kg_add, kg_invalidate, kg_timeline, kg_stats
**Navigation** (4): create_tunnel, list_tunnels, delete_tunnel, follow_tunnels
**Settings** (4): hook_settings, memories_filed_away, reconnect

The server includes:
- **Write-ahead log** (WAL): All write operations logged to `~/.mempalace/wal/write_log.jsonl` with content redaction for sensitive fields
- **Query sanitization** (`query_sanitizer.py`): Strips system prompt contamination from search queries using a 4-step cascade (passthrough -> question extraction -> tail sentence -> tail truncation)
- **Stdio protection**: Redirects stdout to stderr before heavy imports to prevent ChromaDB/ONNX banners from breaking MCP JSON-RPC
- **Argument whitelisting**: Only declared schema properties are passed to handlers

### Normalize Pipeline

`normalize.py` handles 6 input formats:
1. **Plain text with > markers** -- Pass through
2. **Claude Code JSONL** -- Parses message records, merges multi-turn tool loops, strips noise tags
3. **OpenAI Codex CLI JSONL** -- Parses event_msg entries
4. **Claude.ai JSON** -- Flat messages or privacy export with chat_messages
5. **ChatGPT conversations.json** -- Mapping tree traversal
6. **Slack JSON export** -- Multi-party chat with positional role assignment

The `strip_noise()` function removes system tags (`<system-reminder>`, `<command-message>`, etc.), hook output chrome, and Claude Code UI artifacts. All patterns are line-anchored to prevent cross-message content destruction.

### Entity Detection

`entity_detector.py` uses a two-pass heuristic approach with i18n support (14 languages):

**Pass 1 -- Candidate extraction**: Finds capitalized proper nouns appearing 3+ times using language-specific regex patterns (loaded from `i18n/<lang>.json`).

**Pass 2 -- Scoring and classification**:
- Person signals: dialogue markers (3x weight), person verbs (2x), pronoun proximity (2x), direct address (4x)
- Project signals: project verbs (2x), versioned/hyphenated names (3x), code file references (3x)
- Classification requires TWO different signal categories for confident person classification (prevents false positives from e.g., repeated clicking sounds)

---

## Evaluation and Benchmarks

### Benchmark Datasets

MemPalace evaluates on 4 datasets:

| Benchmark | Metric | Score | Notes |
|---|---|---|---|
| LongMemEval (500q) | R@5 | 96.6% (raw), 98.4% (hybrid held-out 450q) | Primary benchmark |
| LoCoMo (1,986q) | R@10 | 60.3% (raw), 88.9% (hybrid v5) | Session-level |
| ConvoMem (250 items) | Avg recall | 92.9% | 50 per category |
| MemBench ACL 2025 (8,500 items) | R@5 | 80.3% | All categories |

### Benchmark Methodology

Benchmarks are fully reproducible from the repository. Scripts in `benchmarks/`:
- `longmemeval_bench.py`
- `locomo_bench.py`
- `convomem_bench.py`
- `membench_bench.py`

Per-question result files are committed under `benchmarks/results_*`.

The project is notably honest about benchmark integrity. They explicitly note that the 100% LongMemEval score involved inspecting 3 specific wrong answers (teaching to the test), and the honest generalized figure is 98.4% on the held-out 450 questions. They also refuse to do side-by-side comparisons with Mem0/Mastra/Zep because different systems publish different metrics.

### Internal Benchmarks

The `tests/benchmarks/` directory contains:
- `test_search_bench.py` -- Search performance
- `test_memory_profile.py` -- Memory profiling
- `test_ingest_bench.py` -- Ingest throughput
- `test_mcp_bench.py` -- MCP tool latency
- `test_recall_threshold.py` -- Recall at various thresholds
- `test_chromadb_stress.py` -- 100K+ drawer stress tests
- `test_palace_boost.py` -- Closet boost effectiveness
- `test_knowledge_graph_bench.py` -- KG query performance

---

## API Design

### CLI Interface

```bash
mempalace init <dir>                    # Initialize palace for a project
mempalace mine <dir>                    # Mine project files
mempalace mine <dir> --mode convos      # Mine conversations
mempalace search "query"                # Search the palace
mempalace wake-up                       # Generate L0+L1 context
mempalace status                        # Show palace statistics
mempalace dedup [--dry-run]             # Remove near-duplicates
mempalace repair                        # Consistency checks
```

### Python API

```python
from mempalace.layers import MemoryStack

stack = MemoryStack(palace_path="~/.mempalace/palace")
context = stack.wake_up(wing="my_project")  # L0+L1
results = stack.search("why did we switch to GraphQL")  # L3

from mempalace.searcher import search_memories
hits = search_memories("query", palace_path="...", wing="...", n_results=5)

from mempalace.knowledge_graph import KnowledgeGraph
kg = KnowledgeGraph()
kg.add_triple("Max", "loves", "chess", valid_from="2025-10-01")
facts = kg.query_entity("Max", as_of="2026-01-15")
```

### MCP Integration

```bash
mempalace-mcp [--palace /path/to/palace]  # Start MCP server
```

All 29 tools are available via JSON-RPC. The key search tool:

```json
{
  "name": "mempalace_search",
  "arguments": {
    "query": "why did we switch to GraphQL",
    "limit": 5,
    "wing": "my_project",
    "max_distance": 1.5
  }
}
```

---

## Strengths

1. **Principled verbatim-first design**. By refusing to summarize, MemPalace avoids the information loss that plagues extract-then-discard systems. The 96.6% R@5 baseline validates that modern embeddings can handle raw text effectively.

2. **Zero-API-key core path**. Everything from ingestion to search runs locally using ChromaDB's built-in sentence-transformers. No cloud dependencies for the primary use case. This is rare among memory systems.

3. **Robust normalization pipeline**. Supporting 6 input formats (Claude Code JSONL, ChatGPT JSON, Codex CLI, Claude.ai, Slack, plain text) with noise stripping and tool output formatting shows real-world polish.

4. **Honest benchmarking**. The project clearly distinguishes retrieval recall from QA accuracy, maintains held-out evaluation sets, and commits reproducible per-question results. The refusal to make misleading cross-system comparisons is commendable.

5. **Backend abstraction with typed results**. The `BaseBackend`/`BaseCollection` contract in `backends/base.py` with `QueryResult`/`GetResult` dataclasses is well-designed. The backward-compatible dict shim (`_DictCompatMixin`) enables gradual migration.

6. **MCP server quality**. 29 tools, stdio protection, argument whitelisting, write-ahead logging, query sanitization. The MCP integration is production-grade.

7. **Knowledge graph with temporal validity**. The `valid_from`/`valid_to` design on triples is practical and handles fact invalidation cleanly. SQLite is the right choice for local-first deployment.

8. **Multi-stage retrieval**. The closet-boost-as-signal-not-gate pattern is well-reasoned -- weak closets cannot degrade the baseline vector search.

9. **Comprehensive test suite**. 53 test files, ~15K lines, 85% coverage threshold. Tests cover edge cases like HNSW stale segments, BLOB seq_id migration, and mtime precision.

10. **Concurrency safety**. File-level mine locks (`mine_lock()`), thread-safe knowledge graph, atomic tunnel saves, inode-based cache invalidation.

---

## Weaknesses

1. **No automatic forgetting or decay**. Memories accumulate forever. There is no importance-based retention, time-decay scoring (mentioned in ROADMAP but not implemented), or garbage collection. For long-running palaces with 100K+ drawers, this will cause retrieval degradation and storage bloat.

2. **Naive chunking**. The 800-char fixed window with 100-char overlap is a blunt instrument. There is no semantic chunking (splitting at topic boundaries), no code-aware chunking (splitting at function/class boundaries), and no adaptive chunk sizing based on content density. The paragraph-boundary preference helps, but many chunks will still split mid-thought.

3. **No embedding model configurability in the core path**. The system uses whatever embedding ChromaDB defaults to (all-MiniLM-L6-v2). There is no abstraction for swapping embedding models, no support for domain-specific models, and no way to use better models (e.g., BGE, E5, GTE) without modifying ChromaDB configuration externally.

4. **Closet extraction is weak**. The regex-based closet builder (`build_closet_lines()`) only catches action verbs from a hardcoded list and section headers. It misses implicit topics, contextual references, and non-English content. The project acknowledges this -- `closet_llm.py` exists as an opt-in LLM path, but the default closets add limited value for narrative content.

5. **Knowledge graph is manually populated**. There is no automatic extraction of entities and relationships from ingested content. The KG must be populated via explicit MCP tool calls (`mempalace_kg_add`) or seeded from a fact-checker config. This significantly limits its utility -- most users will never build a rich KG.

6. **Single-collection architecture**. All drawers from all wings/rooms go into a single ChromaDB collection (`mempalace_drawers`). Metadata filtering scopes queries, but the HNSW index is global. At scale (100K+ drawers), this means every search traverses the entire graph. Separate collections per wing would enable more efficient scoped searches.

7. **No MMR (Maximal Marginal Relevance) or diversity in results**. Search returns the top-N most similar results, which may all come from the same source file or topic. There is no diversity mechanism to ensure results span different wings, rooms, or time periods.

8. **The Layer 1 generation is simplistic**. `Layer1.generate()` fetches all drawers (up to 2000), sorts by an `importance` metadata field that is almost never set (defaults to 3), and truncates to 15 snippets. Without explicit importance scoring, Layer 1 is essentially random sampling from the palace.

9. **Room detection is fragile**. `detect_room()` uses folder path matching, filename matching, and content keyword scoring against room definitions from `mempalace.yaml`. For conversation mining, `detect_convo_room()` uses hardcoded keyword lists (`TOPIC_KEYWORDS`). Neither approach handles ambiguous content well, and there is no learning or feedback loop.

10. **The AAAK dialect adds complexity without clear benefit in the default path**. The README's 96.6% benchmark is from "raw mode, not AAAK mode." The dialect is primarily used for diary entries and the closet index layer, but diary entries stored in AAAK format embed poorly (the MCP server has a TODO comment acknowledging this). The compression is lossy by design, and it is unclear when the tradeoff is worthwhile.

11. **No cross-session deduplication coordination**. The `sweeper.py` module and `convo_miner.py` can ingest the same content under different IDs. The comment in `sweeper.py` acknowledges: "Follow-up: add uniform ingest_mode + message metadata to the primary miners so dedup spans both paths." This is still unresolved.

12. **Global singleton backend**. `palace.py` creates `_DEFAULT_BACKEND = ChromaBackend()` at module load time. This makes testing harder and prevents per-palace backend selection at runtime.

---

## Key Files

| File | Lines | Description |
|---|---|---|
| `mempalace/mcp_server.py` | 1714 | MCP server with 29 tools, WAL, query sanitization, stdio protection |
| `mempalace/dialect.py` | 1092 | AAAK dialect encoder/decoder for lossy summarization |
| `mempalace/miner.py` | 875 | Project file mining with gitignore support, room detection, chunking |
| `mempalace/searcher.py` | 506 | Hybrid search: vector + closet boost + BM25 re-ranking |
| `mempalace/palace_graph.py` | 502 | Graph traversal, tunnel management (passive and explicit) |
| `mempalace/convo_miner.py` | 503 | Conversation mining with exchange-pair chunking |
| `mempalace/layers.py` | 503 | 4-layer memory stack (L0 identity, L1 essential, L2 on-demand, L3 search) |
| `mempalace/entity_detector.py` | 591 | Multi-language entity detection with i18n regex patterns |
| `mempalace/normalize.py` | 589 | Format detection and normalization for 6 chat export formats |
| `mempalace/general_extractor.py` | 522 | Regex-based extraction of decisions, preferences, milestones, problems, emotions |
| `mempalace/knowledge_graph.py` | 442 | Temporal entity-relationship graph in SQLite |
| `mempalace/backends/chroma.py` | 641 | ChromaDB backend with HNSW quarantine and migration fixes |
| `mempalace/backends/base.py` | 370 | Storage backend contract (BaseCollection, BaseBackend, typed results) |
| `mempalace/sources/base.py` | 246 | Source adapter plugin contract (RFC 002) |
| `mempalace/config.py` | 295 | Configuration with input validation and sanitization |
| `mempalace/dedup.py` | 238 | Near-duplicate drawer detection and removal |
| `mempalace/sweeper.py` | 348 | Message-granular Claude Code JSONL ingestion with cursor-based resume |
| `mempalace/palace.py` | 344 | Shared palace operations: collection access, closet building, file locking |
| `mempalace/query_sanitizer.py` | 189 | System prompt contamination mitigation for search queries |
| `mempalace/closet_llm.py` | ~200 | Optional LLM-powered closet generation via OpenAI-compatible endpoints |

---

## Implications for Hippocampus

### Patterns to Adopt

1. **Verbatim-first storage with optional summarization layers**. MemPalace demonstrates that keeping original text and building index layers on top outperforms extract-and-discard. Hippocampus should store verbatim content at the base layer and build semantic indexes separately.

2. **Pluggable backend abstraction**. The `BaseBackend`/`BaseCollection` contract is clean and minimal. Hippocampus should adopt a similar abstraction from the start, supporting ChromaDB, PostgreSQL+pgvector, and potentially SQLite+FTS5 for lightweight deployments.

3. **Multi-stage retrieval with BM25 hybrid**. The vector + BM25 convex combination with configurable weights is effective and well-established. The "signal, not gate" pattern for secondary indexes is a good architectural principle.

4. **Temporal knowledge graph**. The `valid_from`/`valid_to` design is simple and effective for tracking evolving facts. Hippocampus should include temporal validity from the start, but with automatic extraction rather than manual population.

5. **MCP as the primary integration surface**. MemPalace's 29-tool MCP server demonstrates that MCP is the right integration protocol for LLM-facing memory systems.

### Patterns to Improve

1. **Implement automatic memory consolidation**. MemPalace's lack of forgetting/decay is a significant gap. Hippocampus should implement time-decay scoring, importance-based retention, and periodic consolidation (merging related memories, promoting frequently-accessed ones).

2. **Use semantic chunking**. Replace fixed-window chunking with topic-boundary-aware segmentation. Consider using the LLM to identify natural break points, or at minimum detect semantic shifts via embedding similarity between adjacent sentences.

3. **Automatic knowledge graph population**. Instead of relying on manual `kg_add` calls, automatically extract entity-relationship triples from ingested content. This can use the entity detector as a starting point but needs relationship extraction (even heuristic-based).

4. **Embedding model abstraction**. Make the embedding model a first-class configurable component, separate from the storage backend. Support swapping between sentence-transformers, BGE, E5, etc.

5. **Diversity in retrieval**. Implement MMR or a similar diversity mechanism to ensure search results cover different aspects of a query rather than returning near-duplicate hits from the same source.

6. **Per-wing or per-project collections**. Instead of a single global collection with metadata filtering, consider separate vector indexes per wing/project to improve search performance at scale.

7. **Address the L1 importance scoring problem**. The current Layer 1 generation is effectively random because `importance` metadata is almost never set. Hippocampus should compute importance scores automatically based on access frequency, emotional markers, temporal relevance, and entity density.
