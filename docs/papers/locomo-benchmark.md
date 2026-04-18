# LoCoMo: Evaluating Very Long-Term Conversational Memory of LLM Agents

## Paper Metadata

- **Title**: Evaluating Very Long-Term Conversational Memory of LLM Agents
- **Authors**: Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, Yuwei Fang
- **Venue**: ACL 2024 (Long Paper)
- **Date**: February 2024 (arXiv), July 2024 (ACL)
- **arXiv**: https://arxiv.org/abs/2402.17753
- **Website**: https://snap-research.github.io/locomo/
- **GitHub**: https://github.com/snap-research/locomo
- **Citations**: 374+ (as of April 2026)

## Key Insight

LoCoMo is the most widely-used benchmark for evaluating long-term conversational memory in LLM agents. It provides 10 very long conversations (avg. 300 turns, 9K tokens, up to 35 sessions each) with structured annotations for question answering, event summarization, and multimodal dialog generation. It is the de facto standard that systems like Mem0, ReadAgent, MemGPT, and others benchmark against.

---

## 1. Dataset Overview

### Scale
- **10 conversations** total (the dataset is called `locomo10`)
- Each conversation averages **~300 turns** (600 turns in the ACL version) and **~9K-16K tokens**
- Conversations span **up to 32-35 sessions** (simulating multi-day interactions)
- 9x longer than MSC (Multi-Session Chat), 6x more turns, 4x more sessions
- Conversations are between pairs of named characters (e.g., "Audrey" and "Andrew")

### Generation Pipeline
- Uses LLMs to generate long-term conversations conditioned on character personas
- Conversations include temporal markers (dates/times) across sessions
- Some conversations include multimodal elements (shared images with captions)

### Total QA Annotations
- **1,986 QA pairs** total across all 10 conversations
- **1,540 non-adversarial** questions (categories 1-4)
- **446 adversarial** questions (category 5)

---

## 2. Data Format (JSON Schema)

The dataset is stored in a single file: `data/locomo10.json`

Each top-level element represents one conversation. The structure is:

```json
[
  {
    "conversation_id": "conv_01",
    "speaker1": "Audrey",
    "speaker2": "Andrew",
    "conversation": [
      {
        "session_id": 1,
        "date": "2023-01-15",
        "turns": [
          {
            "turn_id": 1,
            "speaker": "Audrey",
            "text": "Hey Andrew! How was your weekend?",
            "type": "text"
          },
          {
            "turn_id": 2,
            "speaker": "Andrew", 
            "text": "It was great! I went hiking at...",
            "type": "text"
          }
        ]
      }
    ],
    "qa_pairs": [
      {
        "question": "What activity did Andrew do last weekend?",
        "answer": "Andrew went hiking.",
        "category": 4,
        "evidence": ["session_1_turn_2"],
        "evidence_text": ["It was great! I went hiking at..."]
      }
    ],
    "event_summary": {
      "events": [
        {
          "description": "Andrew went hiking over the weekend",
          "participants": ["Andrew"],
          "session": 1
        }
      ]
    },
    "observation": "..."
  }
]
```

### Key Fields per Conversation
| Field | Description |
|-------|-------------|
| `conversation` | List of sessions, each with dated turns |
| `qa_pairs` | QA annotations with question, answer, category, evidence |
| `event_summary` | Annotated event graph for summarization task |
| `observation` | Additional observations / persona notes |

### Key Fields per QA Pair
| Field | Description |
|-------|-------------|
| `question` | The question string |
| `answer` | Ground truth answer string |
| `category` | Integer 1-5 indicating question type |
| `evidence` | References to turns that support the answer |
| `evidence_text` | The actual text of the supporting turns |

---

## 3. Question Categories (5 Types)

The `category` field maps to these reasoning types:

| Category ID | Name | Count | Description |
|-------------|------|-------|-------------|
| 1 | **Multi-hop** | ~188 | Requires synthesizing information from **multiple sessions** |
| 2 | **Temporal** | ~181 | Requires understanding time, sequence, or duration |
| 3 | **Open-domain** | ~96 | Hypothetical / inference questions ("Would Andrew enjoy...?") |
| 4 | **Single-hop** | ~841 | Direct fact retrieval from a **single session** (largest category) |
| 5 | **Adversarial** | ~446 | Questions about things never discussed (expected answer: "not mentioned" / unanswerable) |

**Note on category numbering**: The original repo/paper did not explicitly document the category ID mapping. It was clarified in [GitHub Issue #6](https://github.com/snap-research/locomo/issues/6) and confirmed by the [locomo-audit](https://github.com/dial481/locomo-audit) project.

### Distribution Notes
- Category 4 (single-hop) dominates with ~55% of non-adversarial questions
- Category 5 (adversarial) is often excluded from evaluation by many systems
- When people report "LoCoMo score" they typically mean average F1 across categories 1-4 (1,540 questions)

---

## 4. Evaluation Tasks

LoCoMo defines **three evaluation tasks**:

### Task 1: Question Answering (Primary)
- Given the full conversation history, answer questions about it
- 1,986 questions across 5 categories
- This is the task most systems benchmark against
- The system receives the conversation (or retrieves relevant parts) and must answer each question

### Task 2: Event Summarization
- Given the conversation, extract a structured summary of key events
- Uses the `event_summary` annotations as ground truth
- Evaluates whether the system can identify and describe significant events across sessions

### Task 3: Multimodal Dialog Generation
- Generate the next response in the conversation given the history
- Some conversations include shared images (with captions)
- Less commonly evaluated than QA

---

## 5. Evaluation Metrics

### Primary Metrics for QA Task

| Metric | Description |
|--------|-------------|
| **Token-level F1** | Overlap between predicted and gold answer tokens (precision/recall/F1). The **official primary metric**. |
| **BLEU-1** | Unigram-level BLEU score measuring lexical overlap |
| **LLM-as-a-Judge** | GPT-4 (or similar) judges if the generated answer is CORRECT or WRONG given the gold answer |

### How Token-level F1 Works
```python
# Tokenize prediction and gold answer
pred_tokens = normalize(prediction).split()
gold_tokens = normalize(gold_answer).split()

# Calculate overlap
common = Counter(pred_tokens) & Counter(gold_tokens)
num_common = sum(common.values())

precision = num_common / len(pred_tokens)
recall = num_common / len(gold_tokens)
f1 = 2 * precision * recall / (precision + recall)
```

### For Event Summarization
- ROUGE-L (longest common subsequence F1)
- Custom event-graph matching metrics

### For Dialog Generation
- BLEU scores
- Human evaluation (in the original paper)

### Known Issues with Metrics
- The LLM-as-a-Judge approach has been found to accept up to **63% of intentionally wrong answers** ([locomo-audit](https://github.com/dial481/locomo-audit))
- Token-level F1 can be gamed by verbose answers
- Different systems use different subsets (some exclude adversarial, some include)
- The [Reddit discussion](https://www.reddit.com/r/MachineLearning/comments/1s8osi9/) highlights that evaluation methods vary significantly across papers

---

## 6. Evaluation Code

The official repo provides evaluation code in `task_eval/evaluation_stats.py`:

```python
# Key files in the repo
data/locomo10.json          # The dataset
data/locomo10_qa.json       # QA-only subset (convenience)
task_eval/evaluation_stats.py  # Evaluation metrics computation
```

The evaluation script:
1. Loads `locomo10.json` (ground truth) and a predictions file
2. Computes per-category F1 and BLEU-1 scores
3. Optionally runs LLM-as-a-Judge evaluation
4. Reports category-wise and overall aggregated scores

### Simplified Evaluation Harness (EasyLocomo)
[playeriv65/EasyLocomo](https://github.com/playeriv65/EasyLocomo) provides a streamlined evaluation framework that is easier to integrate.

### Third-party Evaluation Harness
[lancedb/locomo-eval](https://github.com/lancedb/locomo-eval) provides a minimal harness for benchmarking memory systems against LoCoMo.

---

## 7. How to Run Against LoCoMo (Step-by-Step)

### Step 1: Download the Dataset
```bash
git clone https://github.com/snap-research/locomo.git
# Dataset is at: locomo/data/locomo10.json
```

### Step 2: Load the Data
```python
import json

with open("data/locomo10.json", "r") as f:
    conversations = json.load(f)

for conv in conversations:
    # Each conv has: conversation (sessions/turns), qa_pairs, event_summary
    for qa in conv["qa_pairs"]:
        question = qa["question"]
        gold_answer = qa["answer"]
        category = qa["category"]   # 1-5
        evidence = qa.get("evidence", [])
```

### Step 3: Generate Predictions
For each conversation, either:
- Feed the **full conversation** as context (full-context baseline)
- Use **RAG** to retrieve relevant turns, then answer
- Use a **memory system** (Mem0, your system, etc.) to process sessions incrementally, then answer

### Step 4: Evaluate
```python
# Token-level F1
def compute_f1(prediction: str, gold: str) -> float:
    pred_tokens = prediction.lower().split()
    gold_tokens = gold.lower().split()
    common = set(pred_tokens) & set(gold_tokens)
    if len(common) == 0:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)
```

### Step 5: Report Results
Report F1 scores **per category** and **overall average**:
```
| Category    | F1    |
|-------------|-------|
| Single-hop  | XX.X% |
| Multi-hop   | XX.X% |
| Temporal    | XX.X% |
| Open-domain | XX.X% |
| Adversarial | XX.X% |
| Overall     | XX.X% |
```

---

## 8. Baseline Results (Collected from Multiple Papers)

### From APEX-MEM (April 2026) - LLM-as-Judge Accuracy
| Method | Single-hop | Multi-hop | Temporal | Open-domain | Adversarial | Overall |
|--------|-----------|-----------|----------|-------------|-------------|---------|
| Full-Context GPT-4o | 88.53% | 77.70% | 71.88% | 92.70% | N/A | 87.52% |
| Full-Context Claude Sonnet | - | - | - | - | - | 62.2% |

### Approximate F1 Scores (from various sources)
| System | Overall F1 | Notes |
|--------|-----------|-------|
| Full-Context (GPT-4o) | ~60% | Upper bound for context-window approach |
| Standard RAG | ~45-55% | Depends on chunking/retrieval |
| Mem0 | ~67% | Published ECAI 2025 |
| ReadAgent | - | Tested in original paper |
| MemoryBank | - | Tested in original paper |
| Open-source memory (Reddit claim) | ~80% | Self-reported |
| APEX-MEM | ~87.5% | LLM-as-judge metric (April 2026) |

**Important caveat**: These numbers are hard to compare directly because:
- Some use F1, others use LLM-as-judge accuracy
- Some include adversarial, others exclude it
- Different base LLMs (GPT-4, GPT-4o, Claude, etc.)
- Mem0's ECAI 2025 numbers may use different evaluation methodology

---

## 9. Known Issues and Limitations

### Ground Truth Quality (locomo-audit)
- A [systematic audit](https://github.com/dial481/locomo-audit) found **156 ground truth issues** across 1,540 non-adversarial questions
- **99 are confirmed errors** (6.4% error rate)
- Wrong answers, ambiguous questions, missing evidence
- The LLM-as-a-Judge accepts up to 63% of intentionally wrong answers

### Benchmark Gaming Concerns
- Category 4 (single-hop) is 55% of non-adversarial questions and easiest to score well on
- Systems that excel at simple retrieval look disproportionately good
- Adversarial questions (category 5) are often excluded, hiding weaknesses
- Token-level F1 rewards verbose answers that happen to contain the right tokens

### Scale Limitations
- Only 10 conversations -- very small dataset
- Results can be noisy with so few samples
- Some systems may overfit to this specific data

### LoCoMo-Plus Extension
- [LoCoMo-Plus](https://arxiv.org/html/2602.10715v1) extends the benchmark with "beyond-factual" cognitive memory evaluation
- Adds commonsense reasoning, emotional understanding, and preference tracking

---

## 10. Practical Implications for Hippocampus

### For Evaluation
1. LoCoMo is the minimum benchmark we should evaluate against -- it is the community standard
2. Download from GitHub (`data/locomo10.json`), implement token-level F1 and LLM-as-judge
3. Report per-category F1 scores (all 5 categories) for transparency
4. Be aware of the ~6.4% ground truth error rate

### For Architecture Design
1. **Single-hop dominates** (55%): Good retrieval is table stakes
2. **Multi-hop is hard** (~20%): Need to connect facts across sessions
3. **Temporal reasoning** (~12%): Must track when events happened relative to each other
4. **Adversarial** (~23%): System must know when information was NOT discussed
5. **Open-domain** (~6%): Requires inference beyond stated facts

### For Implementation
1. Process conversations session-by-session (simulating real-time ingestion)
2. Store memories with temporal metadata (session dates)
3. Retrieve relevant memories given a question
4. Generate answers using retrieved memories as context
5. Compare against gold answers using F1 and LLM-as-judge

### Recommended Evaluation Pipeline
```
1. Load locomo10.json
2. For each conversation:
   a. Feed sessions sequentially to memory system
   b. For each qa_pair:
      - Query memory system with question
      - Collect generated answer
3. Compute metrics:
   - Token-level F1 per category
   - BLEU-1 per category  
   - LLM-as-judge accuracy per category
4. Report per-category and overall scores
```

---

## References

- [Maharana et al., ACL 2024] "Evaluating Very Long-Term Conversational Memory of LLM Agents"
- [APEX-MEM, 2026] "Agentic Semi-Structured Memory with Temporal Reasoning"
- [HingeMem, 2026] "Boundary Guided Long-Term Memory with Query Adaptive Retrieval"
- [locomo-audit] https://github.com/dial481/locomo-audit
- [EasyLocomo] https://github.com/playeriv65/EasyLocomo
- [locomo-eval] https://github.com/lancedb/locomo-eval
- [LoCoMo-Plus] https://arxiv.org/html/2602.10715v1
