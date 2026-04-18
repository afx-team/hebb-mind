# MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks

## Paper Metadata

- **Title**: MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks
- **Authors**: Zexue He\*, Yu Wang\*, Churan Zhi\*, Yuanzhe Hu\*, Tzu-Ping Chen\*, Lang Yin\*, Ze Chen, Tong Arthur Wu, Siru Ouyang, Zihan Wang, Jiaxin Pei, Julian McAuley (\* = equal contribution)
- **Affiliations**: (1) UC San Diego, (2) multiple affiliated institutions -- see paper for full list
- **Date**: February 2026 (arXiv: 2602.16313)
- **arXiv**: https://arxiv.org/abs/2602.16313
- **PDF**: https://arxiv.org/pdf/2602.16313
- **HTML**: https://arxiv.org/html/2602.16313v1
- **Website**: https://memoryarena.github.io/
- **HuggingFace Dataset**: https://huggingface.co/datasets/ZexueHe/memoryarena
- **GitHub Code**: No official code repository released as of April 2026 (community has requested it via HuggingFace discussions thread #2)
- **Related Repo**: https://github.com/HUST-AI-HYZ/MemoryAgentBench (ICLR 2026 paper by overlapping authors -- Yuanzhe Hu, Yu Wang, Julian McAuley)
- **Format**: JSON on HuggingFace, < 1K examples
- **Stanford Digital Economy Lab**: https://digitaleconomy.stanford.edu/publication/memoryarena-benchmarking-agent-memory-in-interdependent-multi-session-agentic-tasks/

## Key Insight

MemoryArena is the first benchmark that evaluates agent memory in the context of **action-taking** rather than isolated recall. Existing benchmarks either test memorization (recall QA over past conversations) or test agentic action (tool use, code execution) -- but separately. MemoryArena unifies these into a "Memory-Agent-Environment" (MAE) loop where memory must directly inform sequential decision-making across multiple sessions with causally dependent subtasks. Current SOTA models (including GPT, Claude) achieve consistently low success rates (typically 40-60%), revealing that high scores on memory recall benchmarks do not translate to effective memory-guided action.

---

## 1. Core Concept: Memory-Agent-Environment (MAE) Loop

### The Problem with Existing Benchmarks
- **Memorization benchmarks** (LoCoMo, LongMemEval, etc.): Test recall over static long-context inputs via QA, but do not test whether memory improves downstream decisions.
- **Agentic benchmarks** (SWE-bench, WebArena, etc.): Test tool use and action, but tasks are independent -- no cross-session memory is needed.
- **Gap**: No benchmark tests whether memory acquired in Session N helps the agent act correctly in Session N+k.

### MAE Loop Design
MemoryArena introduces a cyclic evaluation pattern:

1. **Agent receives a subtask** (Session t)
2. **Agent acts in the environment** (e.g., searches, navigates, plans)
3. **Environment returns feedback** (success/failure, observations, constraints discovered)
4. **Agent must store relevant information in memory**
5. **Next session (t+1)**: Agent receives a new subtask that **causally depends** on outcomes/observations from session t
6. **Agent must retrieve from memory** to correctly complete the new subtask

The key innovation: subtasks are **explicitly interdependent** -- later subtasks cannot be solved correctly without information acquired from earlier sessions.

---

## 2. Four Evaluation Environments (Domains)

MemoryArena instantiates the MAE loop across four distinct domains, each testing different aspects of memory-dependent reasoning. The project website categorizes these as: **web navigation**, **preference-constrained planning**, **progressive information search**, and **sequential formal reasoning**.

### 2.1 Bundled Web Shopping (Web Navigation)
- **Setting**: Agent purchases related products across multiple sessions on a simulated e-commerce site
- **Memory challenge**: Later purchases must consider **compatibility** with previously purchased items (e.g., buying a phone case that fits the phone bought in Session 1)
- **Interdependency**: Each purchase constrains future options; agent must remember product specs, brands, and compatibility requirements
- **Environment**: Simulated web shopping interface with search, browse, and purchase actions

### 2.2 Preference-Constrained Group Travel Planning
- **Setting**: Agent plans group travel across multiple sessions, where each session introduces new group member preferences and constraints
- **Memory challenge**: Must reconcile potentially conflicting preferences (budget, destination, dietary restrictions, schedule) from all group members across sessions
- **Interdependency**: Session N reveals preferences of traveler N; the final plan must satisfy ALL accumulated constraints
- **Environment**: Planning interface with search for flights, hotels, restaurants, activities

### 2.3 Progressive Information Searching (Progressive Web Search)
- **Setting**: Agent conducts multi-step research where each session involves searching for information that builds on previous findings
- **Memory challenge**: Must track chains of evidence, refine hypotheses, and avoid re-searching already-found information
- **Interdependency**: Search queries and results in later sessions depend on what was discovered earlier
- **Environment**: Simulated web search interface

### 2.4 Sequential Formal Reasoning (Math)
- **Setting**: Agent solves a sequence of mathematical/logical problems where each problem's solution depends on results from earlier problems
- **Memory challenge**: Must precisely recall intermediate results (numbers, proofs, derivations) from prior sessions
- **Interdependency**: Problem N uses the answer from Problem N-1 as an input
- **Environment**: Formal reasoning environment with step-by-step verification

---

## 3. Dataset Format and Structure

### Data Access
```python
from datasets import load_dataset
ds = load_dataset("ZexueHe/memoryarena")
```

### Dataset Schema
Each row in the HuggingFace JSONL file represents one agentic task (a dict) with multiple subtasks, their corresponding answers, and background information.

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique identifier for each agentic task entry |
| `task_type` | string | One of the four domain types (web shopping, travel planning, information search, formal reasoning) |
| `questions` | list[str] | Ordered list of subtask prompts/questions (one per session) |
| `answers` | list[str] | Corresponding ground-truth answers for each subtask |
| `context` / `misc` | string/dict | Background context, environmental details, or miscellaneous information needed for the task |

### Dataset Scale
- **Format**: JSONL (JSON Lines)
- **Size**: < 1K total examples (relatively small, human-crafted benchmark)
- **Modality**: Text
- **Tasks are human-crafted** with explicitly designed causal interdependencies between subtasks
- Each task contains multiple subtasks (sessions), each with its own question and answer
- The benchmark prioritizes quality and difficulty of interdependencies over raw quantity

### Key Design Properties
1. **Causal dependencies are explicit**: The benchmark is designed so that subtask N+1 *cannot* be solved without information from subtask N
2. **Human-crafted**: Not automatically generated -- each task is carefully designed by humans
3. **Multi-session structure**: Each task spans multiple sessions (not just one long context)
4. **Actionable**: Agents must take actions in simulated environments, not just answer questions

---

## 4. Evaluation Protocol

### Agent Architecture Under Test
MemoryArena evaluates three classes of memory-augmented agents:

1. **Long-Context Agents**: Entire conversation history is passed as context (tests whether raw context window is sufficient)
2. **RAG Agents**: Retrieval-augmented generation where past session logs are indexed and retrieved
3. **Memory Agents**: Dedicated memory module (separate "memory agent") that reads/writes structured memory

The benchmark uses a **two-agent architecture**:
- **Task Agent**: Executes actions in the environment
- **Memory Agent**: Manages memory read/write operations, summarization, and retrieval

### Evaluation Metrics

#### Task Progress Score (PS)
The primary metric. Measures the **fraction of subtasks completed** within a task:

```
PS = (number of subtasks completed correctly) / (total number of subtasks in the task)
```

- PS captures **partial progress** -- even if an agent fails the full task, it gets credit for completed subtasks
- A subtask is "completed" if the agent's action matches the ground-truth answer (exact match or LLM-judged equivalence)
- PS is averaged across all tasks in a domain, then across domains

#### Success Rate (SR)
- Binary: 1 if ALL subtasks in a task are completed, 0 otherwise
- Much stricter than PS -- tests whether agent can complete the full chain of interdependent subtasks

#### Per-Domain Reporting
- Results are reported per domain (shopping, travel, search, reasoning) as well as aggregated
- This allows identifying which types of memory-dependent reasoning are hardest

### Evaluation Flow
1. For each task in the dataset:
   a. Initialize the environment and memory
   b. For each subtask (session) in order:
      - Present the subtask prompt to the agent
      - Agent may read from memory
      - Agent takes actions in the environment
      - Environment returns feedback
      - Agent may write to memory
      - Evaluate agent's final answer against ground truth
   c. Compute PS and SR for the task
2. Aggregate scores per domain and overall

---

## 5. Key Results and Findings

### Main Finding: SOTA Models Fail
- Current state-of-the-art LLMs and augmented memory systems achieve **consistently low success rates** on MemoryArena
- Models that score well on memorization benchmarks (e.g., LoCoMo) often plummet to **40-60%** on MemoryArena
- This demonstrates that **memory recall ability does not equal memory utilization ability**

### Result Patterns
- **Long-context agents** struggle because raw context windows become noisy with accumulated session histories
- **RAG agents** struggle because retrieval often fails to surface the specific piece of information needed for the causal dependency
- **Memory agents** perform somewhat better but still far from perfect, suggesting memory writing/summarization loses critical details

### Why Models Fail
1. **Information loss during memory write**: Agents fail to record the right details from environment feedback
2. **Retrieval mismatch**: The information needed for subtask N+1 is not what a similarity search naturally retrieves from subtask N's logs
3. **Cascading errors**: One failed subtask causes all downstream dependent subtasks to fail (since they depend on the previous result)
4. **Context pollution**: In long-context mode, irrelevant session histories distract from the critical information

---

## 6. Comparison with Other Memory Benchmarks

| Aspect | MemoryArena | LoCoMo | LongMemEval | MemBench |
|--------|------------|--------|-------------|----------|
| **What it tests** | Memory-guided action across sessions | Memory recall in conversation QA | Long-term memory retrieval | General memory capabilities |
| **Task type** | Multi-session agentic tasks with causal deps | QA over long conversations | QA over long conversation histories | Various memory tasks |
| **Action required?** | Yes (environment interaction) | No (QA only) | No (QA only) | No (QA only) |
| **Cross-session deps?** | Yes (explicit causal chains) | No (independent questions) | Partial (temporal) | No |
| **Domains** | 4 (shopping, travel, search, reasoning) | 1 (conversation) | 1 (conversation) | Multiple |
| **Size** | < 1K (human-crafted) | 10 conversations | ~500 QA pairs | ~1K+ |
| **Key insight** | Memory recall != memory utilization | Need for long-term memory | Temporal reasoning is hard | Comprehensive evaluation |

---

## 7. Code Availability and Reproducibility

### Current Status (April 2026)
- **Dataset**: Available on HuggingFace at `ZexueHe/memoryarena` (JSON format, < 1K rows)
- **Evaluation code**: NOT publicly released yet. A HuggingFace discussion thread (discussion #2) explicitly requests the source code and evaluation environment. The simulated environments (web shopping, travel planner, etc.) appear to be custom-built and not yet open-sourced.
- **Related code**: The same research group has a related repo `HUST-AI-HYZ/MemoryAgentBench` (ICLR 2026) which evaluates memory in LLM agents via incremental multi-turn interactions and may share infrastructure

### To Evaluate Against MemoryArena
Without official evaluation code, you would need to:
1. Load dataset from HuggingFace: `load_dataset("ZexueHe/memoryarena")`
2. Implement or simulate the four environments
3. Build the MAE loop (session iteration, memory read/write, action execution)
4. Implement PS and SR scoring
5. The biggest challenge is **recreating the simulated environments** (especially bundled web shopping and travel planning)

### Programmatic Dataset Access
```python
# Install: pip install datasets
from datasets import load_dataset

# Load full dataset
ds = load_dataset("ZexueHe/memoryarena")

# Iterate over tasks
for task in ds["test"]:  # or ds["train"] depending on split
    task_id = task["id"]
    task_type = task["task_type"]
    questions = task["questions"]   # list of subtask prompts
    answers = task["answers"]       # list of ground-truth answers
    context = task.get("context") or task.get("misc")  # background info
    
    # Process each session (subtask) sequentially
    for session_idx, (question, answer) in enumerate(zip(questions, answers)):
        # Run your agent on `question` with access to memory
        # Compare agent output to `answer`
        pass
```

---

## 8. Implications for Hippocampus

### Direct Relevance
MemoryArena is highly relevant because it tests exactly what hippocampus aims to solve: **making memory useful for downstream agent actions**, not just retrieval.

### Design Lessons
1. **Memory writing matters as much as reading**: Agents need to proactively extract and store the right information after each interaction, not just dump raw logs
2. **Causal dependency tracking**: A memory system should understand which memories are prerequisites for which tasks -- this is similar to hippocampus-style memory consolidation
3. **Structured memory > raw text**: The cascading failure mode suggests that structured, queryable memory (not just text summaries) would help
4. **Memory relevance scoring**: Traditional similarity-based retrieval fails; need task-aware retrieval that understands causal chains

### Evaluation Strategy
- MemoryArena would be an excellent **stretch benchmark** for hippocampus -- if we can improve PS scores, it demonstrates genuine memory utility
- However, the lack of released evaluation environments is a blocker
- In the short term, LoCoMo (released, well-supported) is better for baseline evaluation; MemoryArena for advanced/aspirational testing
- Monitor the HuggingFace discussions for code release

### Key Metrics to Target
- **Task Progress Score (PS)**: The partial-credit metric is most useful for development iteration
- **Success Rate (SR)**: The strict metric for final benchmarking
- Compare long-context baseline vs. hippocampus-augmented agent to demonstrate value-add
