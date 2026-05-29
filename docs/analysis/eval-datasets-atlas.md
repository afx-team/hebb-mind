# Eval Dataset Atlas

Six long-term-memory benchmarks we run (or plan to run) Hebb Mind against. This document records schema, distribution, distinctive design choices, and what each dataset actually stresses — grounded in the local copies at `eval/data/`, not just the upstream READMEs.

The goal: when picking which benchmark to lean on for a given decision (retriever change, reranker change, consolidation tweak), this page tells you which dataset's failure modes will actually move.

---

## Quick reference

| Dataset | Items | Haystack size (median) | Primary scoring | What it stresses | Hebb status |
|---|---|---|---|---|---|
| **LongMemEval** | 500 questions | 50 sessions / 494 turns / q | session-level Recall@k + LLM judge | needle-in-haystack across many sessions, knowledge update | runnable |
| **ConvoMem** | 600 questions | 1.2 sessions / 47 turns / q | turn-level Recall@k + LLM judge (rubric) | 6 typed evidence modes (recall, abstain, update, implicit) | runnable |
| **LoCoMo** | 10 conversations / 1986 QA | 27 sessions / 588 turns / convo | LLM judge | 5 reasoning categories incl. adversarial | runnable |
| **MemBench** | 1000 (noisy/movie slice) | 8 sessions / 171 turns / row | turn-level Hit@k + 4-way MCQ accuracy | 11 noise/aggregation categories | runnable |
| **PersonaMem** | 589 questions / 37 shared contexts | 25k tokens (shared 32k corpus) | 4-way MCQ accuracy | persona evolution + distance-controlled retrieval | runnable |
| **MemoryArena** | 701 scenarios / 4850 subtasks | varies per split | task Success Rate + Progress Score (exact match) | agentic multi-subtask state carryover | data-only (loader & runner TBD) |

---

## 1. LongMemEval — single-question needle, multi-session haystack

**Source**: `xiaowu0162/longmemeval` (HF). Local: `eval/data/longmemeval/longmemeval_s.json` (500 items).

**Schema** (one row = one question with its own private haystack):

```
question_id, question, answer, question_date, question_type,
haystack_session_ids[], haystack_dates[], haystack_sessions[],
answer_session_ids[]   ← THE ground truth for Recall@k
```

**Distribution**:

| field | min | mean | max |
|---|---|---|---|
| sessions per question | 39 | 50.2 | 66 |
| turns per question | 396 | 494 | 616 |
| `answer_session_ids` per q | 1 | 1.9 | 6 |

Question-type breakdown (the 6 official categories):

```
multi-session           133
temporal-reasoning      133
knowledge-update         78
single-session-user      70
single-session-assistant 56
single-session-preference 30
```

**Distinctive features**:

- **Each question carries its own haystack.** No shared corpus — different questions have different historical conversations. This rules out cross-question caching of any kind.
- **Session is the scoring unit.** R@k matches on `answer_session_ids`, not turn ids. A memory system that retrieves the right session but a wrong turn within it still counts.
- **`question_date` matters.** Temporal-reasoning questions ask "what did I say last Wednesday" — the memory metadata must carry per-session timestamps or these answers are unrecoverable.

**What it stresses**: retrieval scale (50× sessions) + temporal grounding. A purely lexical retriever struggles on multi-session reasoning; a purely embedding retriever struggles on temporal-reasoning. Where Hebb Mind's 3-path RRF base shines.

---

## 2. ConvoMem — typed failure modes, tiny haystack

**Source**: `convomem` benchmark. Local: `eval/data/convomem/convomem.json` (600 items).

**Schema** (per row):

```
question, answer, message_evidences[{speaker, text}], conversations[{messages[]}],
category, _category_key, personId, use_case_model_name, core_model_name
```

**Distribution**:

| field | min | median | mean | max |
|---|---|---|---|---|
| sessions/q | 1 | 1 | 1.2 | 3 |
| messages/q | 8 | 46 | 47.1 | 156 |
| evidences/q | 1 | 1 | 1.2 | 3 |
| question chars | 18 | 92 | 102 | 327 |
| answer chars | 1 | 80 | 214 | 1289 |

Two orthogonal partitions:

```
category (life domain):       Professional 308   Personal 292
_category_key (evidence type): 6 types × 100 each
```

The **6 evidence types** are the core taxonomy:

| Type | Tests | Answer shape |
|---|---|---|
| `user_evidence` | Recall a fact the **user** stated | short |
| `assistant_facts_evidence` | Recall what the **assistant** previously said | short |
| `changing_evidence` | Info changed mid-conversation — return the latest state | short |
| `abstention_evidence` | Question that **cannot** be answered from history | fixed refusal template |
| `preference_evidence` | Recommend consistent with stated preferences | rubric (~500 chars) |
| `implicit_connection_evidence` | Connect facts that don't share lexical surface | rubric |

**Distinctive features**:

- **The 100×6 design isolates failure modes.** Most other datasets blur "couldn't find evidence" with "found it but generated wrong answer." Here, the `abstention` slice specifically punishes hallucination; `assistant_facts` punishes pipelines that only ingest user turns.
- **Persona collapse.** 525/600 rows are `Telemarketer` — lexical distributions are narrow (lead/CRM/spreadsheet/follow-up). Hacks tuned on this won't generalize.
- **Mostly single-session** (median 1). Don't use ConvoMem as a stand-in for LongMemEval-style multi-session reasoning. The exception: `changing_evidence` is the only slice that systematically uses 2 sessions to encode the update.
- **Two answer regimes.** First 4 types: short factual; LLM judge can be strict. Last 2 types: rubric; judge must score against a paragraph, not a string.

**What it stresses**: precision in retrieving the right turn out of ~47, and the LLM's ability to abstain when the right turn doesn't exist.

---

## 3. LoCoMo — long, organic, adversarial

**Source**: LoCoMo (Maharana et al.). Local: `eval/data/locomo/locomo10.json` (10 conversations).

**Schema** (one row = one full conversation + ~199 QA):

```
sample_id, conversation{speaker_a, speaker_b, session_N, session_N_date_time},
qa[{question, answer, evidence[dia_id], category, adversarial_answer?}],
event_summary{events_session_N}, observation{session_N_observation}, session_summary
```

**Distribution**:

- 10 conversations, 1986 total QA pairs (~199 per conversation)
- Sessions per conversation: min 19, mean **27.2**, max 32
- Turns per conversation: min 369, mean **588**, max 689

QA category breakdown:

```
cat 1 — single-hop          282
cat 2 — temporal             321   ("When did Caroline go to ...")
cat 3 — multi-hop             96
cat 4 — commonsense/open-domain  841
cat 5 — adversarial          446   ← no `answer` field, only `adversarial_answer`
```

**Distinctive features**:

- **The only multi-month organic dataset.** Sessions are timestamped weeks apart; LongMemEval's are synthetic. Real conversational drift, off-topic chatter, callbacks.
- **`dia_id` evidence pointers.** Each QA cites specific turns like `"D2:8"` (session 2, dialog 8). Lets you score turn-level retrieval, not just session-level.
- **Category 5 is a trap.** No `answer` field — only `adversarial_answer`, which is the *wrong* answer a sloppy system would produce. Scoring code must reject any match to `adversarial_answer`.
- **Extra annotations (`event_summary`, `observation`, `session_summary`) are gifts, not requirements.** They let you build oracle-memory baselines without doing your own summarization.

**What it stresses**: long-horizon retrieval on real conversational structure. Our [[locomo-raw-91pct]] result on this dataset (37.6% → 91.0% via 7 ordered retrieval fixes) is the strongest internal signal we have that the retrieval stack works.

---

## 4. MemBench — turn-level recall with controlled noise

**Source**: `import-myself/Membench` (FirstAgent subset). Local default: `eval/data/membench/membench_noisy_movie.json` (1000 rows; the `noisy` × `movie` slice).

**Schema** (per row):

```
tid, message_list[ [turn, ...], ...],     ← list of sessions, each a list of {user, assistant, sid, time?}
QA{question, answer, choices{A,B,C,D}, ground_truth, target_step_id[[sid, ...], ...]}
```

**Distribution (noisy/movie slice)**:

- 1000 rows
- **All rows are multi-session** (median 8 sessions, ~171 turns per row)
- `ground_truth` is a single letter A/B/C/D (4-way MCQ)
- `target_step_id` is a list of `[sid_or_global_idx, ...]` pointing at the evidence turn(s)

The **11 categories** in the broader benchmark (we currently run `noisy` by default):

```
simple   highlevel   knowledge_update   comparative   conditional   noisy
aggregative   highlevel_rec   lowlevel_rec   RecMultiSession   post_processing
```

**Distinctive features**:

- **MCQ + turn-id evidence dual scoring.** Hit@k against `target_step_id` measures retrieval; MCQ accuracy measures end-to-end. Separating these is rare.
- **`noisy` is the hardest slice on purpose.** Distractors (similar topics, contradictory throwaway lines) interleaved with signal. MemPalace's published 43.4% on this slice is the lowest of their 11 categories — confirms it's the right slice for retrieval-quality work.
- **`sid` vs `global_idx` ambiguity.** The dataset is inconsistent about whether `target_step_id` points to per-turn `sid` or cross-session global index. Our adapter (`eval/datasets/membench.py:244`) checks both at scoring time.

**What it stresses**: turn-level precision under distraction. The ideal benchmark for testing reranker improvements.

---

## 5. PersonaMem — persona evolution with distance control

**Source**: PersonaMem. Local: `eval/data/personamem/personamem.json` (589 questions) + `shared_contexts_32k.jsonl` (37 shared 32k-token corpora).

**Schema**:

```
persona_id, question_id, question_type, topic,
context_length_in_tokens, context_length_in_letters,
distance_to_ref_in_blocks, distance_to_ref_in_tokens,
num_irrelevant_tokens, distance_to_ref_proportion_in_context,
user_question_or_message, correct_answer, all_options,
shared_context_id, end_index_in_shared_context
```

**Distribution**:

| field | min | mean | max |
|---|---|---|---|
| context tokens | 15,560 | 24,846 | 29,539 |
| distance to reference (tokens) | 1,597 | 15,615 | 28,862 |

- 20 personas, 37 shared contexts (~32k tokens each), 13 topics
- 7 question types:

```
track_full_preference_evolution      139
recall_user_shared_facts             129
recalling_the_reasons_behind_previous_updates  99
suggest_new_ideas                     93
generalizing_to_new_scenarios         57
provide_preference_aligned_recommendations  55
recalling_facts_mentioned_by_the_user 17
```

Top topics: `movieRecommendation` (104), `datingConsultation` (94), `financialConsultation` (72), `travelPlanning` (71), `bookRecommendation` (67).

**Distinctive features**:

- **Distance is explicit.** Every question records exactly how many tokens lie between the reference turn and the query — a controlled variable other datasets don't expose. Lets you plot accuracy-vs-distance directly.
- **Shared corpora.** 37 base contexts shared across 589 questions, so you can ingest each corpus once and run 16 queries against it. Cheaper than LongMemEval's per-question haystacks.
- **MCQ scoring.** Answer is a single letter `(a)`–`(d)`; trivially exact-match. No LLM judge needed.
- **The 7 question types are about evolution, not just recall.** `track_full_preference_evolution` and `recalling_the_reasons_behind_previous_updates` test temporal/causal understanding — *why* the user's stance changed, not just *what* it is now.

**What it stresses**: behavior over long contexts (15k–28k tokens between question and evidence) and whether the memory system preserves the *sequence* of preference updates, not just the latest state.

---

## 6. MemoryArena — agentic multi-subtask, brand-new failure mode

**Source**: `ZexueHe/memoryarena` (HF, CC-BY-4.0). Local: `eval/data/memoryarena/{5 configs}.json` (data only — no loader, no runner yet).

**5 configs, all using HF `test` split**:

| config | rows | subtasks/row (mean) | total subtasks |
|---|---|---|---|
| `bundled_shopping` | 150 | 6 (fixed) | 900 |
| `progressive_search` | 221 | 7.4 (range 4–16) | 1641 |
| `group_travel_planner` | 270 | 6.9 (range 5–9) | 1869 |
| `formal_reasoning_math` | 40 | 8.8 (range 2–16) | 354 |
| `formal_reasoning_phys` | 20 | 4.3 (range 2–12) | 86 |
| **total** | **701** | | **4850** |

**Schema** (varies per split):

```
common:   id, questions[], answers[]
+ math/phys:    backgrounds[], paper_name      ← bg[i] is the "environment observation" for subtask i; mostly empty
+ travel:       base_person{name, query, daily_plans[]}
+ shopping:     category
```

**Distinctive features**:

- **Subtasks are interdependent.** Not "read history, answer one question" — each row is a sequence where later subtasks reference earlier results. Examples:
  - `group_travel_planner`: subtask 2 says *"For day 1, I want to stay at the same place as Emma"* — must remember Emma's choice from subtask 1.
  - `bundled_shopping`: subtask 1 frosting must be compatible with subtask 0 cake base; budget $70 is a running global state.
  - `formal_reasoning_phys`: subtask 0 establishes setup once, then 77% of remaining subtasks have **empty `backgrounds`** — agent must recall from memory.
- **Memory has a *write moment*: `backgrounds[i]`.** When non-empty, that string is the environment's hand-off to the agent for subtask `i`. In math, 68% are empty; in phys, 77% — meaning the answer-relevant material has to come from memory, not from the prompt.
- **Exact-match scoring with structured answers.** ASIN strings for shopping, multi-day itinerary dicts for travel, formula values like `(c_2,c_3,c_0)=(-1,-1,-16)` for physics. No LLM judge ambiguity.
- **All off-the-shelf memory systems fail.** Reported SR for Mem0 = 0.14, Letta = 0.15, long-context GPT-5.1-mini = 0.16. The dataset paper's framing: *"agents with near-saturated performance on LoCoMo perform poorly here"*.

**What it stresses**: state carryover across long agentic loops. Different from every other dataset in this atlas — failure is "broke the dependency chain," not "couldn't find the turn."

**Integration cost**: 2 of the 5 splits (`formal_reasoning_math/phys`, 60 rows) are pure text and runnable offline. The other 3 need WebShop / TravelPlanner / web-search environments standing up, which the official harness has not yet published. See `eval/datasets/memoryarena.py` — downloader is done, loader and runner are open.

---

## Coverage matrix: what each dataset actually tests

| Capability | LongMemEval | ConvoMem | LoCoMo | MemBench | PersonaMem | MemoryArena |
|---|---|---|---|---|---|---|
| Cross-session retrieval | ✅ (50 sess) | partial | ✅ (27 sess) | ✅ (8 sess) | ✅ (32k tok) | varies |
| Turn-level precision | session only | ✅ | ✅ via dia_id | ✅ | turn id | n/a |
| Temporal reasoning | ✅ | weak | ✅ | weak | partial | n/a |
| Knowledge update | ✅ slice | ✅ slice | implicit | ✅ slice | ✅ slice | partial |
| Abstention / no-evidence | weak | ✅ slice | weak | weak | weak | weak |
| Implicit / connect-the-dots | partial | ✅ slice | ✅ cat 3 | weak | ✅ types | ✅ |
| Long context (>20k tokens) | ✅ | no | ✅ | partial | ✅ explicit | varies |
| **Agentic state carryover** | no | no | no | no | no | ✅ only |
| Adversarial / trap answers | weak | weak | ✅ cat 5 | weak | weak | weak |
| Persona / preference evolution | weak | weak | partial | weak | ✅ | partial |

The matrix has one diagonal: **MemoryArena is the only agentic test**. The other 5 are variations on conversational QA. If we ever ship a Hebb Mind that an agent uses end-to-end, MemoryArena is the only dataset that will catch regressions in that scenario.

---

## Recommended evaluation order for Hebb Mind

1. **LoCoMo + LongMemEval** — primary signal. Long, multi-session, established baselines. Our [[locomo-raw-91pct]] and the LongMemEval R@5=96.6% comparison are the headlines.
2. **MemBench (noisy slice)** — best for reranker / retrieval-precision changes. Turn-level Hit@k separates retrieval from generation cleanly.
3. **ConvoMem** — diagnostic, not headline. Run when you change abstention behavior, knowledge-update handling, or assistant-side ingestion. Don't chase its average score in isolation — the 6 slices need to be reported separately.
4. **PersonaMem** — useful when changes touch persona / preference handling. Distance-controlled curves are unique here.
5. **MemoryArena (math + phys first)** — start with the 60 offline rows. This is the only dataset where we can show Hebb Mind beating Mem0 / Letta on something they fundamentally can't do well. Worth the integration cost.

## Known distribution traps

- **LongMemEval `temporal-reasoning` slice (27%)**: failing here usually means session timestamps aren't on memory metadata, not that retrieval is broken.
- **ConvoMem Telemarketer dominance (87.5%)**: hacks tuned on ConvoMem rarely generalize. Re-check on LongMemEval before celebrating.
- **LoCoMo only 10 conversations**: high variance on small slices. Don't claim a +1pp improvement is real without all 10.
- **MemBench `target_step_id` is sid OR global_idx depending on file**: scoring must check both.
- **PersonaMem 4-way MCQ**: random baseline is 25%. A 50% system isn't impressive — read the per-question-type breakdown.
- **MemoryArena SR vs PS**: SR (all subtasks pass) is harsh — 0.00 is common even for strong systems. PS (fraction passed) is the right thing to optimize early.
