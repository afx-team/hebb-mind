# MemPalace Benchmark Deep Dive

## Overview

This document provides a comprehensive, source-code-level analysis of MemPalace's benchmark methodology: which embedding models are used, how retrieval/recall is computed, what datasets are evaluated, and how each scoring improvement was built. The goal is to enable Hippocampus to replicate or contrast its own evaluation fairly.

---

## 1. Embedding Models

### Default: ChromaDB Built-in (all-MiniLM-L6-v2)

The baseline and all primary reported scores use **ChromaDB's default embedding function**, which is `sentence-transformers/all-MiniLM-L6-v2`:

- **Dimensions**: 384
- **Max tokens**: 256
- **Size**: ~80 MB
- **Space**: cosine distance (HNSW)

In the codebase, this is the implicit default — when no `--embed-model` flag is passed and no `embedding_function` is specified in `create_collection()`, ChromaDB loads all-MiniLM-L6-v2 automatically. The benchmark scripts call `collection.query(query_texts=[question], ...)` which triggers ChromaDB's built-in embedding.

### Optional: fastembed Models (via `--embed-model` flag)

The `longmemeval_bench.py` and `locomo_bench.py` scripts support swapping the embedding model via the `--embed-model` CLI argument. The `_make_embed_fn()` function in `longmemeval_bench.py` (lines 104-143) maps short names to HuggingFace model IDs:

| CLI Flag | HuggingFace Model ID | Dimensions | Size |
|----------|---------------------|------------|------|
| `default` | (ChromaDB built-in: all-MiniLM-L6-v2) | 384 | ~80 MB |
| `bge-base` | BAAI/bge-base-en-v1.5 | 768 | ~400 MB |
| `bge-large` | BAAI/bge-large-en-v1.5 | 1024 | ~1.3 GB |
| `nomic` | nomic-ai/nomic-embed-text-v1.5 | 768 | ~550 MB |
| `mxbai` | mixedbread-ai/mxbai-embed-large-v1 | 1024 | ~1.3 GB |

In `locomo_bench.py`, the embed support is simpler: `_embed()` function (lines 60-65) uses `fastembed.TextEmbedding` with a model name passed directly, defaulting to `BAAI/bge-large-en-v1.5`. The LoCoMo benchmark reports a bge-large hybrid result at 92.4% R@10 (vs. 60.3% with default embeddings).

**Key finding**: Better embeddings alone provide a significant boost. On LoCoMo, switching from all-MiniLM-L6-v2 to bge-large-en-v1.5 improved single-hop recall from ~49% to ~65% — a +16pp jump without any heuristic scoring.

### Production System (searcher.py)

The production `search_memories()` in `searcher.py` uses the default ChromaDB embedding (all-MiniLM-L6-v2) with no model-swapping capability. The search pipeline is:

```
Query → ChromaDB vector search (3× over-fetch) → Closet boost → BM25 hybrid re-rank
```

Hybrid re-ranking formula (from `searcher.py` lines 112-147):

```python
vector_sim = max(0.0, 1.0 - distance)        # cosine distance → similarity
score = 0.6 * vector_sim + 0.4 * bm25_norm    # convex combination
```

BM25 uses Okapi-BM25 with k1=1.5, b=0.75, Lucene-style smoothed IDF, min-max normalized within the candidate set.

---

## 2. Benchmark Datasets

### 2.1 LongMemEval

- **Source**: `xiaowu0162/longmemeval-cleaned` on HuggingFace
- **Size**: 500 questions
- **Format**: Each entry contains `haystack_sessions` (conversation history), `haystack_session_ids`, `haystack_dates`, `question`, `question_date`, and ground-truth answer session IDs
- **Question types** (6 categories):

| Type | Count | Description |
|------|-------|-------------|
| Knowledge update | 78 | Facts that changed over time |
| Multi-session | 133 | Information across multiple sessions |
| Temporal reasoning | 133 | Time-anchored queries ("last month") |
| Single-session user | 70 | Questions about user's own statements |
| Single-session preference | 30 | Questions about implied preferences |
| Single-session assistant | 56 | Questions about what the AI said |

- **Metric**: Recall@k (R@k) — whether the correct session ID appears in the top-k retrieved results. Also reports NDCG@k.
- **Granularity**: Session-level (one document per session, all user turns concatenated) or turn-level (one document per user turn). Primary results use session granularity.

### 2.2 LoCoMo

- **Source**: `snap-research/locomo` (GitHub)
- **Size**: 10 conversations, ~1,986 QA pairs
- **Format**: Multi-session personal conversations with 5 categories
- **Categories**:

| ID | Category |
|----|----------|
| 1 | Single-hop |
| 2 | Temporal |
| 3 | Temporal-inference |
| 4 | Open-domain |
| 5 | Adversarial |

- **Metric**: Retrieval Recall@k at session level
- **Granularity**: dialog (per-turn) or session (per-session). Primary results use session granularity.
- **Note**: Each conversation has 19-32 sessions. Top-k=50 exceeds the session count, making retrieval trivially easy — the honest baseline is top-k=10.

### 2.3 ConvoMem

- **Source**: Salesforce/ConvoMem on HuggingFace
- **Size**: 75,336 items across 6 evidence categories (benchmark samples 50-100 per category)
- **Categories**: user_evidence, assistant_facts_evidence, changing_evidence, abstention_evidence, preference_evidence, implicit_connection_evidence
- **Metric**: Retrieval recall — whether the evidence message text appears in top-k results (substring matching)
- **Special note**: Uses `EphemeralClient` (in-memory), no hybrid scoring, no LLM rerank. Pure ChromaDB default embedding retrieval.

### 2.4 MemBench (ACL 2025)

- **Source**: `import-myself/Membench` (GitHub), paper at ACL 2025
- **Size**: ~8,500 items across 11 categories
- **Format**: Multi-turn conversations with QA pairs containing `target_step_id` — the specific turn(s) containing the answer
- **Categories**:

| Category | Description |
|----------|-------------|
| simple | Single-turn fact recall |
| highlevel | Inferences across turns |
| knowledge_update | Facts that change over time |
| comparative | Comparing items across turns |
| conditional | Conditional reasoning |
| noisy | Distractors mixed in |
| aggregative | Combining multi-turn info |
| highlevel_rec | High-level recommendations |
| lowlevel_rec | Low-level recommendations |
| RecMultiSession | Cross-session recommendations |
| post_processing | Post-processing tasks |

- **Metric**: Hit@k (boolean) — whether any target turn's `sid` or `global_idx` appears in the top-k retrieved results
- **Topic filter**: Primarily evaluated on "movie" topic
- **Uses hybrid mode** (keyword overlap re-ranking, weight=0.50) by default

---

## 3. Retrieval Pipeline — Detailed Breakdown

### 3.1 Raw Mode (Baseline: 96.6% R@5 on LongMemEval)

The simplest possible pipeline:

```
Raw text → ChromaDB add (documents) → ChromaDB query (query_texts) → Return top-k
```

- **Chunking**: One document per session (all user turns concatenated with `\n`). Turn granularity optionally available.
- **Embedding**: ChromaDB default (all-MiniLM-L6-v2), cosine distance, HNSW
- **Query**: `collection.query(query_texts=[question], n_results=50)`
- **No post-processing**: Results ranked purely by cosine similarity
- **No LLM calls**: Entirely local, zero cost

This is the "verbatim storage + embeddings" core claim. 483/500 questions answered correctly.

### 3.2 Hybrid v1 (97.8% R@5: +1.2pp)

Adds keyword overlap re-ranking on top of semantic search:

```python
# Extract keywords from query (stop words removed, 3+ chars only)
query_keywords = extract_keywords(question)

# For each retrieved document:
overlap = keyword_overlap(query_keywords, doc)  # fraction of keywords found
fused_dist = dist * (1.0 - 0.30 * overlap)      # up to 30% distance reduction
```

- Over-fetches 3× (n_results=50 for top-5)
- Default weight: 0.30 (validated on full 500 questions; 0.40 showed no improvement)
- No temporal processing, no LLM calls

### 3.3 Hybrid v2 (98.4% R@5: +0.6pp)

Three targeted fixes on top of hybrid v1:

**Fix 1 — Temporal date boost** (for time-anchored questions):

```python
# Parse "N weeks ago", "a month ago", etc. from question
days_offset, tolerance = parse_time_offset_days(question)
target_date = question_date - timedelta(days=days_offset)

# For sessions near the target date: up to 40% distance reduction
if delta_days <= tolerance:
    temporal_boost = 0.40                                    # full boost
elif delta_days <= tolerance * 3:
    temporal_boost = 0.40 * (1 - (delta_days - tolerance) / (tolerance * 2))  # partial
else:
    temporal_boost = 0.0
fused_dist *= (1.0 - temporal_boost)
```

Supports: "N days ago", "a couple days ago", "yesterday", "a week ago", "N weeks ago", "last week", "a month ago", "N months ago", "last month", "last year", "a year ago", "recently".

**Fix 2 — Two-pass for assistant-reference questions**:

If query contains triggers like "you suggested", "you told me", "what did you":
1. Pass 1: Query user-turns-only index → top-5 sessions
2. Pass 2: Re-index those 5 sessions with full text (user + assistant) → re-query

This avoids diluting the semantic signal while enabling assistant-turn retrieval.

**Fix 3 — Preference broadening**: Expands query with synonym-domain keywords for single-session-preference questions.

### 3.4 Hybrid v3 (99.4% R@5 with Haiku rerank: +0.6pp v2→v3)

**Fix 1 — Preference extraction at ingest time** (16 regex patterns):

```python
PREF_PATTERNS = [
    r"i've been having (?:trouble|issues?|problems?) with X",
    r"i've been feeling X",
    r"i prefer X",
    r"i usually X",
    r"i want to X",
    # ... 11 more patterns
]
```

Creates synthetic documents like `"User has mentioned: preference for X"` with the same corpus_id as the original session. These bridge vocabulary gaps between question phrasing and session text.

**Fix 2 — Expanded LLM rerank pool**: From top-10 to top-20 candidates. Catches cases where the correct session was at rank 11-12.

### 3.5 Hybrid v4 (100% R@5 with Haiku/Sonnet rerank: +0.6pp v3→v4)

Three targeted fixes for the three remaining failures:

**Fix 1 — Quoted phrase extraction** (60% distance reduction):
If the question contains text in single/double quotes, sessions containing that exact phrase get a 60% distance boost.

**Fix 2 — Person name boosting** (20-40% distance reduction):
Capitalized proper nouns extracted from the query; sessions mentioning that name get a distance reduction.

**Fix 3 — Nostalgia/memory patterns** (new preference patterns):
Added: "I still remember X", "I used to X", "when I was in high school X", "growing up X".

**Important caveat**: These three fixes were designed by inspecting the exact 3 failing questions — this is teaching to the test. The held-out 450-question evaluation gives 98.4% R@5, which is the honest generalizable figure.

### 3.6 Production Search (searcher.py)

The production system's `search_memories()` implements a different pipeline from the benchmark:

```
Stage 1: ChromaDB vector search (3× over-fetch)
Stage 2: Closet boost (signal, not gate)
Stage 3: Drawer-grep enrichment (neighbor chunks)
Stage 4: BM25 hybrid re-rank (0.6 vector + 0.4 BM25)
Stage 5: (Optional) LLM rerank — benchmark only
```

**Closet boost** is unique to production: Closet hits use rank-based distance reduction `[0.40, 0.25, 0.15, 0.08, 0.04]` for ranks 0-4, but only for closets with cosine distance < 1.5. This is the "signal, not gate" principle — weak closets can only help, never hurt.

**BM25 implementation**: Full Okapi-BM25 (k1=1.5, b=0.75) with Lucene-style IDF smoothing `log((N - df + 0.5) / (df + 0.5) + 1)`, min-max normalized within candidate set.

### 3.7 LLM Rerank (Optional Final Stage)

All benchmark scripts support `--llm-rerank` which takes the top-K candidates and asks an LLM to pick the most relevant one:

```python
# Prompt (from longmemeval_bench.py):
prompt = (
    f"Question: {question}\n\n"
    f"Which of the following passages most directly answers this question? "
    f"Reply with just the number (1-{len(candidates)}).\n\n"
    + numbered_candidate_summaries[:500_chars_each]
)
```

- **Models tested**: Claude Haiku (default, ~$0.001/query), Claude Sonnet (~$0.003/query), Ollama (local, any model)
- **Pool size**: Top-10 (LongMemEval), top-10 (LoCoMo)
- **Single pick, not full ranking**: The chosen candidate is promoted to rank 1; remaining order preserved
- **Graceful degradation**: API failure returns original ranking unchanged

---

## 4. Score Summary by Dataset

### LongMemEval (500 questions, session granularity)

| Mode | R@5 | R@10 | NDCG@10 | LLM? | Honest? |
|------|-----|------|---------|------|---------|
| Raw ChromaDB (all-MiniLM-L6-v2) | 96.6% | 98.2% | 0.889 | No | Yes |
| Hybrid v1 (keyword overlap) | 97.8% | 98.8% | 0.930 | No | Yes |
| Hybrid v2 (temporal + 2-pass) | 98.4% | 99.0% | 0.934 | No | Yes |
| Hybrid v2 + Haiku rerank | 98.8% | 99.0% | 0.966 | Haiku | Yes |
| Hybrid v3 + Haiku rerank | 99.4% | 99.6% | 0.975 | Haiku | Yes |
| Hybrid v4 + Haiku rerank | **100%** | — | 0.976 | Haiku | **No** (3 q's tuned) |
| Hybrid v4 held-out 450q | **98.4%** | **99.8%** | 0.939 | No | **Yes** |

**LongMemEval per-type breakdown (raw baseline):**

| Question Type | R@5 | R@10 |
|--------------|-----|------|
| Knowledge update | 99.0% | 100% |
| Multi-session | 98.5% | 100% |
| Temporal reasoning | 96.2% | 97.0% |
| Single-session user | 95.7% | 97.1% |
| Single-session preference | 93.3% | 96.7% |
| Single-session assistant | 92.9% | 96.4% |

### LoCoMo (1,986 questions, session granularity)

| Mode | R@10 | LLM? | Honest? |
|------|------|------|---------|
| Raw (all-MiniLM-L6-v2) | 60.3% | No | Yes |
| Hybrid v5 (no rerank) | 88.9% | No | Yes |
| bge-large hybrid (no rerank) | 92.4% | No | Yes |
| bge-large + Haiku rerank | 96.3% | Haiku | Yes |
| Hybrid v5 + Sonnet rerank (top-50) | 100% | Sonnet | **No** (top-k > sessions) |

**LoCoMo hybrid v5 per-category (top-10, no LLM):**

| Category | R@10 |
|----------|------|
| Single-hop | 72.1% |
| Temporal | 90.8% |
| Temporal-inference | 70.0% |
| Open-domain | 92.6% |
| Adversarial | 95.3% |

### ConvoMem (50 items/category sampled)

| Category | Recall |
|----------|--------|
| Assistant Facts | 100% |
| User Facts | 98.0% |
| Abstention | 91.0% |
| Implicit Connections | 89.3% |
| Preferences | 86.0% |
| **Average** | **92.9%** |

Pure ChromaDB default embedding, no hybrid, no LLM.

### MemBench (ACL 2025, ~8,500 items, movie topic, hybrid mode, top-5)

| Category | R@5 |
|----------|-----|
| aggregative | 99.3% |
| comparative | 98.4% |
| knowledge_update | 96.0% |
| simple | 95.9% |
| highlevel | 95.8% |
| lowlevel_rec | 99.8% |
| highlevel_rec | 76.2% |
| post_processing | 56.6% |
| conditional | 57.3% |
| **noisy** | **43.4%** |
| **Overall** | **80.3%** |

Hybrid mode with keyword overlap weight=0.50, bge-large not tested.

---

## 5. Benchmark Integrity Notes

### Train/Test Split

MemPalace explicitly acknowledges that the hybrid v4's 100% score on LongMemEval involves overfitting:

- The 3 fixes (quoted phrase, person name, nostalgia patterns) were designed by examining the exact 3 failing questions
- A 50/450 dev/held-out split (`lme_split_50_450.json`, seed=42) was created
- The honest held-out score is **98.4% R@5, 99.8% R@10** on 450 unseen questions
- Only single-session-preference (96.0% R@10) shows misses; all other categories are 100% R@10 on held-out

### LoCoMo top-k Caveat

The 100% LoCoMo result used top-k=50, but each conversation only has 19-32 sessions. This means retrieval is trivially satisfied — the ground truth is always in the candidate pool. The honest LoCoMo number is **88.9% R@10 without LLM rerank**.

### Metric vs Metric

MemPalace measures **retrieval recall** (is the right session in top-k?), NOT end-to-end QA accuracy. Other systems publish QA accuracy:
- Mastra's 94.87% = QA accuracy with GPT-5-mini (different metric)
- Supermemory's ~99% = QA accuracy with 8-/12-agent ensemble
- These are not directly comparable to R@5

---

## 6. Chunking Strategy (Benchmark vs Production)

A key difference between benchmark and production:

**Benchmark**:
- LongMemEval: One document per session (all user turns concatenated) — typically 200-2000 characters
- LoCoMo: One document per session (dialog or session granularity)
- ConvoMem: One document per message
- MemBench: One document per turn pair `[User] ... [Assistant] ...`

**Production** (`miner.py`):
- 800-character fixed window with 100-character overlap
- Paragraph-aware boundary splitting
- Minimum chunk size: 50 characters

The benchmark does NOT use the production chunking strategy. It uses whole-session or whole-turn documents, which are much larger and more semantically coherent than the 800-char chunks in production.

---

## 7. Retrieval Formulas — Complete Reference

### Hybrid v1 Keyword Overlap (LongMemEval, LoCoMo)

```python
query_keywords = extract_keywords(question)  # 3+ chars, no stop words
overlap = keyword_overlap(query_keywords, doc)  # fraction found in doc
fused_dist = cosine_dist * (1.0 - 0.30 * overlap)
```

### Hybrid v4 Full Scoring (LongMemEval)

```python
# 1. Keyword overlap
predicate_kws = keywords - person_names  # separate name vs predicate
name_words = person_names from query

# 2. Scoring
fused_dist = cosine_dist * (1.0 - 0.50 * predicate_overlap)  # 50% for predicates
if quoted_phrase_match:
    fused_dist *= (1.0 - 0.60)  # 60% for quoted phrases
if name_match:
    fused_dist *= (1.0 - 0.20)  # 20% for person names
```

### LoCoMo Hybrid v5 (Same as LongMemEval v4 but with weight differences)

```python
fused_dist = dist * (1.0 - 0.50 * predicate_overlap)
if quoted_boost > 0:
    fused_dist *= (1.0 - 0.60 * quoted_boost)
if name_boost > 0:
    fused_dist *= (1.0 - 0.20 * name_boost)
```

Note: LoCoMo uses 0.50 for predicate overlap vs. LongMemEval's 0.30 (v1) — different weights for different datasets.

### Production BM25 Hybrid (searcher.py)

```python
vector_sim = max(0.0, 1.0 - cosine_distance)
score = 0.6 * vector_sim + 0.4 * bm25_normalized
# BM25: k1=1.5, b=0.75, Lucene-style IDF
```

### Closet Boost (production only)

```python
# Closet hits boost drawer rankings (signal, not gate)
boost_schedule = [0.40, 0.25, 0.15, 0.08, 0.04]  # ranks 0-4
# Only applies if closet cosine_distance < 1.5
```

---

## 8. Implications for Hippocampus Benchmarking

### What to Replicate

1. **Session-granularity baseline**: The 96.6% raw baseline is the most important number to replicate or contrast. It proves that verbatim text + default embeddings is a strong foundation.

2. **Embedding model ablation**: Test at least all-MiniLM-L6-v2 and BGE-large. The +16pp jump on LoCoMo single-hop from better embeddings is the cheapest and most reliable improvement.

3. **Hybrid scoring ablation**: The keyword overlap + temporal boost + preference extraction pipeline shows the incremental value of each heuristic. Test each independently.

4. **Held-out evaluation**: Create a proper train/test split before tuning any parameters. The 98.4% vs 100% gap on LongMemEval demonstrates the cost of not doing so.

### What to Improve

1. **Use production chunking in benchmarks**: The benchmark uses whole-session documents; production uses 800-char chunks. The 96.6% baseline may not hold at production chunk sizes.

2. **Test on more diverse datasets**: All four benchmarks are English-language conversation recall. No code search, no document QA, no multilingual.

3. **Report QA accuracy alongside retrieval recall**: Retrieval recall is necessary but not sufficient. A system can retrieve the right session but still answer incorrectly.

4. **Address the noisy category (MemBench 43.4%)**: Verbatim storage with embeddings degrades badly when distractors are embedded alongside signal. This is the clearest weakness and the most important to solve.

5. **Separate embedding quality from pipeline quality**: The production pipeline (closet boost, BM25 hybrid, neighbor expansion) was NOT tested in benchmarks. Benchmark numbers reflect the benchmark pipeline, not production search quality.

### Dataset Access

- **LongMemEval**: `https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json`
- **LoCoMo**: `https://github.com/snap-research/locomo` (data/locomo10.json)
- **ConvoMem**: `https://huggingface.co/datasets/Salesforce/ConvoMem`
- **MemBench**: `https://github.com/import-myself/Membench` (data/FirstAgent/)