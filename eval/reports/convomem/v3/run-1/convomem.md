# Hebb Mind Evaluation Report: ConvoMem

**Eval version**: v3
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
| Correct | 441 |
| **Accuracy** | **73.5%** |
| Avg Latency | 45.5ms |
| Est. Total Time | 27.3s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| abstention_evidence | 99.0% |
| assistant_facts_evidence | 94.0% |
| changing_evidence | 76.0% |
| implicit_connection_evidence | 31.0% |
| preference_evidence | 59.0% |
| user_evidence | 82.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_judge_confidence | 0.969 |
| avg_top1_relevance | 0.313 |

## Error Analysis

Total errors: 159 / 600

### convomem_user_evidence_11_q (user_evidence)
- **Q**: What was the name of the PR firm where you did your unpaid internship after graduation?
- **Expected**: City Voice Media
- **Generated**: I don't know.

### convomem_user_evidence_13_q (user_evidence)
- **Q**: I'm updating my professional profile and need to get the wording just right. Can you remind me of the exact title of the degree I received from university?
- **Expected**: You received a Bachelor of Arts in Communications.
- **Generated**: I don't know.

### convomem_user_evidence_32_q (user_evidence)
- **Q**: Who was the contact from CloudSync that Alex met at the virtual networking event?
- **Expected**: David from CloudSync
- **Generated**: I don't know.

### convomem_user_evidence_36_q (user_evidence)
- **Q**: What was the name of the company where I had a really bad call yesterday?
- **Expected**: Retro Inc.
- **Generated**: I don't know.

### convomem_user_evidence_42_q (user_evidence)
- **Q**: I'm putting together some notes for my calls tomorrow. Remind me, what was that specific common objection I mentioned I've been getting lately?
- **Expected**: The common objection you mentioned you've been getting is, 'Your SaaS solution is too expensive for our current budget.'
- **Generated**: Price objections

## Configuration

```json
{
  "eval_version": "v3",
  "mode": "raw_per_message",
  "metric": "end_to_end_qa_llm_judge",
  "judge_used": true,
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 600
}
```
