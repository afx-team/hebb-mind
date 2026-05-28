# Hebb Mind Evaluation Report: ConvoMem (5×50 1_evidence substring slice)

**Eval version**: v1
**Mode**: raw_per_message_substring
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 250

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 250 |
| Correct | 204 |
| **Accuracy** | **81.6%** |
| Avg Latency | 409.9ms |
| Est. Total Time | 1.7min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| abstention_evidence | 90.0% |
| assistant_facts_evidence | 100.0% |
| implicit_connection_evidence | 52.0% |
| preference_evidence | 72.0% |
| user_evidence | 94.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_evidence_recall | 0.818 |
| avg_top1_relevance | 0.331 |
| perfect_recall_rate | 0.816 |
| recall_abstention_evidence | 0.900 |
| recall_assistant_facts_evidence | 1.000 |
| recall_implicit_connection_evidence | 0.530 |
| recall_preference_evidence | 0.720 |
| recall_user_evidence | 0.940 |
| zero_recall_rate | 0.180 |

## Error Analysis

Total errors: 46 / 250

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

### convomem_abstention_evidence_301_q (abstention_evidence)
- **Q**: What is the specific numerical target for new leads or call volume that Alex needs to hit next quarter, as outlined in the recent team meeting?
- **Expected**: There is no information in prior conversations to answer this question
- **Generated**: 

### convomem_abstention_evidence_302_q (abstention_evidence)
- **Q**: Can you tell me the specific month and year Alex achieved his personal best in sales at StapleSource?
- **Expected**: There is no information in prior conversations to answer this question
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_per_message_substring",
  "metric": "substring_evidence_recall",
  "slice": "1_evidence_x_5_categories",
  "items_per_category": 50,
  "included_categories": [
    "assistant_facts_evidence",
    "user_evidence",
    "abstention_evidence",
    "implicit_connection_evidence",
    "preference_evidence"
  ],
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 250
}
```
