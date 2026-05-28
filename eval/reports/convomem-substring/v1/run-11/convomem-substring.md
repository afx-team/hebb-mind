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
| Correct | 207 |
| **Accuracy** | **82.8%** |
| Avg Latency | 249.8ms |
| Est. Total Time | 1.0min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| abstention_evidence | 90.0% |
| assistant_facts_evidence | 98.0% |
| implicit_connection_evidence | 48.0% |
| preference_evidence | 80.0% |
| user_evidence | 98.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_evidence_recall | 0.836 |
| avg_top1_relevance | 0.328 |
| perfect_recall_rate | 0.828 |
| recall_abstention_evidence | 0.910 |
| recall_assistant_facts_evidence | 0.980 |
| recall_implicit_connection_evidence | 0.510 |
| recall_preference_evidence | 0.800 |
| recall_user_evidence | 0.980 |
| zero_recall_rate | 0.156 |

## Error Analysis

Total errors: 43 / 250

### convomem_assistant_facts_evidence_100_q (assistant_facts_evidence)
- **Q**: I'm finally getting around to that productivity hack you mentioned last week. Can you remind me of the specific automation tool and method you suggested for integrating my color-coded spreadsheet with our company's Salesforce CRM?
- **Expected**: I suggested using Zapier to create an automation. The method involves setting up a 'Zap' where the trigger is a 'New or Updated Spreadsheet Row' in your sheet, and the action is to 'Create or Update a Record' in Salesforce, mapping your spreadsheet columns to the corresponding Salesforce fields.
- **Generated**: 

### convomem_user_evidence_7_q (user_evidence)
- **Q**: What was the name of the late-night campus radio show you hosted during university?
- **Expected**: Midnight Musings
- **Generated**: 

### convomem_abstention_evidence_301_q (abstention_evidence)
- **Q**: What is the specific numerical target for new leads or call volume that Alex needs to hit next quarter, as outlined in the recent team meeting?
- **Expected**: There is no information in prior conversations to answer this question
- **Generated**: 

### convomem_abstention_evidence_302_q (abstention_evidence)
- **Q**: Can you tell me the specific month and year Alex achieved his personal best in sales at StapleSource?
- **Expected**: There is no information in prior conversations to answer this question
- **Generated**: 

### convomem_abstention_evidence_306_q (abstention_evidence)
- **Q**: What brand of dog food does Alex feed Cooper?
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
