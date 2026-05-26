# Hebb Mind Evaluation Report: ConvoMem

**Eval version**: v2
**Mode**: raw_per_message
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 600

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 600 |
| Correct | 399 |
| **Accuracy** | **66.5%** |
| Avg Latency | 48.5ms |
| Est. Total Time | 29.1s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| abstention_evidence | 86.0% |
| assistant_facts_evidence | 93.0% |
| changing_evidence | 64.0% |
| implicit_connection_evidence | 26.0% |
| preference_evidence | 41.0% |
| user_evidence | 89.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_evidence_recall | 0.690 |
| avg_top1_relevance | 0.314 |
| perfect_recall_rate | 0.665 |
| zero_recall_rate | 0.285 |

## Error Analysis

Total errors: 201 / 600

### convomem_user_evidence_7_q (user_evidence)
- **Q**: What was the name of the late-night campus radio show you hosted during university?
- **Expected**: Midnight Musings
- **Generated**: 

### convomem_user_evidence_13_q (user_evidence)
- **Q**: I'm updating my professional profile and need to get the wording just right. Can you remind me of the exact title of the degree I received from university?
- **Expected**: You received a Bachelor of Arts in Communications.
- **Generated**: 

### convomem_user_evidence_42_q (user_evidence)
- **Q**: I'm putting together some notes for my calls tomorrow. Remind me, what was that specific common objection I mentioned I've been getting lately?
- **Expected**: The common objection you mentioned you've been getting is, 'Your SaaS solution is too expensive for our current budget.'
- **Generated**: 

### convomem_user_evidence_58_q (user_evidence)
- **Q**: I'm recommending the shelter where I got Cooper to a colleague, but I'm blanking on the name. Can you remind me what it was called?
- **Expected**: You mentioned that you adopted Cooper from a place called Second Chance Animal Rescue.
- **Generated**: 

### convomem_user_evidence_60_q (user_evidence)
- **Q**: How long did I mention my backpacking trip in Vietnam lasted?
- **Expected**: Three months
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v2",
  "mode": "raw_per_message",
  "metric": "substring_evidence_recall",
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 600
}
```
