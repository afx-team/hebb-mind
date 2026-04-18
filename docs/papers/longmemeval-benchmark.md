# LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory

## Paper Metadata

- **Title**: LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory
- **Authors**: Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu
- **Affiliations**: UCLA, Tencent AI Lab
- **Date**: October 2024 (arXiv), accepted at ICLR 2025
- **arXiv**: [2410.10813](https://arxiv.org/abs/2410.10813)
- **PDF**: [https://arxiv.org/pdf/2410.10813](https://arxiv.org/pdf/2410.10813)
- **GitHub**: [https://github.com/xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval)
- **Project Page**: [https://xiaowu0162.github.io/long-mem-eval/](https://xiaowu0162.github.io/long-mem-eval/)

---

## 1. What is LongMemEval?

LongMemEval is a comprehensive, challenging, and **scalable** benchmark for evaluating the **long-term memory** capabilities of chat assistants. Unlike benchmarks that test single-session understanding, LongMemEval focuses on a chat assistant's ability to recall, reason over, and manage information across **many conversation sessions** accumulated over time.

The key insight is that real-world chat assistants interact with users over weeks and months, accumulating a rich conversational history. LongMemEval tests whether systems can effectively utilize this accumulated history.

---

## 2. Five Core Memory Abilities Evaluated

LongMemEval defines and tests **five core long-term memory abilities**:

| # | Ability | Description |
|---|---------|-------------|
| 1 | **Information Extraction** | Ability to recall specific facts, events, or details mentioned in prior conversations |
| 2 | **Multi-Session Reasoning** | Ability to chain facts/events across multiple separate conversation sessions to derive an answer |
| 3 | **Temporal Reasoning** | Ability to reason about the order, timing, and sequence of events across sessions (e.g., "What happened before X?") |
| 4 | **Knowledge Updates** | Ability to track changes and updates to information over time (e.g., user changed jobs, updated preferences) and return the most current version |
| 5 | **Abstention** | Ability to recognize when a question cannot be answered from the available conversation history and safely refuse rather than hallucinate |

---

## 3. Seven Question Types

The 500 manually curated questions are organized into **seven types** that map onto the five abilities:

| Question Type | Memory Ability | Description |
|---------------|---------------|-------------|
| **Single-hop** | Information Extraction | Direct factual retrieval from a single session |
| **Multi-hop** | Multi-Session Reasoning | Requires chaining 2+ facts across different sessions |
| **Temporal - Ordering** | Temporal Reasoning | Questions about the order/sequence of events |
| **Temporal - Precedence** | Temporal Reasoning | Questions about what happened before/after something |
| **Knowledge Update** | Knowledge Updates | User info changed over time; must return latest |
| **Unanswerable - Never Mentioned** | Abstention | Info was never discussed in any session |
| **Unanswerable - Don't Remember** | Abstention | Info was mentioned but user explicitly said they forgot/don't remember |

---

## 4. Dataset Structure and Scale Variants

### Scale Variants

LongMemEval is designed to be **scalable** -- the same 500 questions are evaluated against different sizes of conversation history context:

| Variant | Sessions per Question | Approx. Tokens | Description |
|---------|----------------------|-----------------|-------------|
| **LongMemEval-S** | 30-50 sessions | ~115k tokens | Small scale; fits in many long-context LLMs |
| **LongMemEval-M** | ~500 sessions | ~1.5M tokens | Medium scale; exceeds most LLM context windows |

The scaling is achieved by mixing in distractor sessions (conversations unrelated to the question) alongside the answer-relevant sessions. This tests whether the system can find needles in an increasingly large haystack of conversations.

### Data Format

The dataset is distributed as compressed archives on HuggingFace. Each question entry contains:

```
Fields per question (inferred from GitHub issues and usage code):
- question_id: Unique identifier
- question: The natural language question
- answer: Ground truth answer(s)
- question_type: One of the seven types above
- ability: Which of the five core abilities it tests
- answer_session_ids: IDs of sessions containing the answer
- chat_history: List of conversation sessions, each session containing:
  - session_id: Unique session identifier
  - turns: List of (user, assistant) turn pairs
    - Each turn may have a "has_answer": true/false flag indicating 
      whether that turn contains answer-relevant information
```

### File Organization

```
data/
  longmemeval_s/     # Small variant (~115k tokens/question, 30-50 sessions)
    question_XXX.json (or combined file)
  longmemeval_m/     # Medium variant (~1.5M tokens/question, ~500 sessions)
    question_XXX.json (or combined file)
```

---

## 5. How to Access the Dataset

### HuggingFace (Recommended - use the cleaned version)

The original dataset had some annotation errors. Use the **cleaned** version:

- **Cleaned (recommended)**: [https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)
- **Original (deprecated)**: [https://huggingface.co/datasets/xiaowu0162/longmemeval](https://huggingface.co/datasets/xiaowu0162/longmemeval)
- **Total size**: ~3.03 GB (compressed)
- **Downloads**: ~8,790/month (cleaned), ~1,041/month (original)

### Download Instructions

From the official GitHub README:

```bash
# Clone the repo
git clone https://github.com/xiaowu0162/LongMemEval.git
cd LongMemEval

# Download from HuggingFace and place in data/ folder
# Option 1: Using huggingface_hub
pip install huggingface_hub
python -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='xiaowu0162/longmemeval-cleaned', 
                 repo_type='dataset', 
                 local_dir='data/')
"

# Option 2: Using git lfs
git lfs install
git clone https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned data/
```

### GitHub Repository

```
https://github.com/xiaowu0162/LongMemEval
```

Contains evaluation scripts, baseline implementations, and instructions.

---

## 6. Evaluation Metrics

### Primary Metric: QA Accuracy via LLM-as-Judge

The official evaluation pipeline uses **GPT-4o as a judge**:

1. **Retrieval**: The system retrieves relevant conversation sessions/passages from the chat history
2. **Generation**: An LLM generates an answer based on the retrieved context
3. **Judging**: GPT-4o compares the generated answer against the ground truth answer and determines semantic correctness (binary: correct/incorrect)

The overall metric is **accuracy** = (number of correctly answered questions) / (total questions).

### Breakdown Reporting

Results are typically reported:
- **Overall accuracy** across all 500 questions
- **Per-ability accuracy** (one score for each of the 5 abilities)
- **Per-question-type accuracy** (one score for each of the 7 types)

### Known Benchmark Scores (as of early 2026)

| System | Accuracy | Notes |
|--------|----------|-------|
| Full-context GPT-4o (baseline) | ~60.2% | All history in context window |
| Zep (RAG-based) | ~71.2% | Using GPT-4o for generation |
| HINDSIGHT (OSS 20B model) | ~83.6% | Published SOTA with smaller model |
| Emergence AI | ~86% | Using GPT-4o-2024-08-06 |
| MemMachine | ~93.0% | LongMemEval-S, with 6 optimization dimensions |
| agentmemory v4 | ~96.2% | Claims highest published score |

### Caveats

A Reddit audit (r/AIMemory) reported some quality issues:
- ~6.4% of answer keys in LongMemEval-S may be incorrect
- The LLM judge (GPT-4o) may accept some intentionally wrong answers (up to 63% in adversarial tests)
- The **cleaned** dataset on HuggingFace addresses some of these issues

---

## 7. Running the Evaluation

### Prerequisites

```bash
# Clone repo and install
git clone https://github.com/xiaowu0162/LongMemEval.git
cd LongMemEval
pip install -r requirements.txt

# Set API keys
export OPENAI_API_KEY=your_key_here  # For GPT-4o judge
```

### Evaluation Pipeline (from third-party implementations)

The typical evaluation loop involves:

1. **Memory Construction**: Ingest all conversation sessions into the memory system being evaluated
2. **Question Answering**: For each of the 500 questions:
   - Present the question to the system
   - System retrieves from its memory store
   - System generates an answer
3. **Scoring**: Use GPT-4o to judge each generated answer against ground truth

Example from the LightMem implementation:

```bash
# Memory construction: add session-based conversations into memory store
# Question answering: retrieve + generate for each question  
# Scoring: GPT-4o judge compares with ground truth
python run_longmemeval.py --data_dir data/longmemeval_s --output_dir results/
```

### Cost Considerations

- Running LongMemEval-S with GPT-4o for both generation and judging costs approximately $10-50 depending on implementation
- LongMemEval-M is significantly more expensive due to ~1.5M tokens per question context
- Pre-caching strategies (batch API calls for extraction) can reduce costs

---

## 8. Implications for Hippocampus

### Why LongMemEval Matters for This Project

1. **Directly relevant benchmark**: LongMemEval tests exactly the capabilities our hippocampus memory system needs -- multi-session recall, temporal reasoning, knowledge updates, and knowing when NOT to answer.

2. **Five abilities map to our architecture needs**:
   - Information Extraction -> Our retrieval/indexing layer must be precise
   - Multi-Session Reasoning -> Our memory must support cross-session linking
   - Temporal Reasoning -> We need temporal metadata on all memories
   - Knowledge Updates -> Our memory must handle overwrites/versioning
   - Abstention -> Our system needs confidence estimation / "I don't know" capability

3. **Scalability testing**: The S/M variants let us test at different scales, which is critical for production readiness.

4. **Standard evaluation**: Using LongMemEval-S (cleaned) as our primary benchmark gives us direct comparability with Zep, Mem0, HINDSIGHT, and other memory systems.

### Recommended Usage

- Use **LongMemEval-S (cleaned)** as the primary evaluation benchmark during development
- Report per-ability breakdowns to identify weak points in our memory architecture
- Target >85% overall accuracy as a competitive baseline
- Be aware of the LLM judge limitations -- consider supplementing with exact-match metrics where possible

---

## References

- [Wu et al., 2024] Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu. "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory." arXiv:2410.10813. ICLR 2025.
- [MemoryAgentBench] ai-hyz/MemoryAgentBench -- unified benchmark framework that incorporates LongMemEval alongside other memory benchmarks.
