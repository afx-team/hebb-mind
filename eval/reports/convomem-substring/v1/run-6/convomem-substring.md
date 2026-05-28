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
| Correct | 0 |
| **Accuracy** | **0.0%** |
| Avg Latency | 4.3ms |
| Est. Total Time | 1.1s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| abstention_evidence | 0.0% |
| assistant_facts_evidence | 0.0% |
| implicit_connection_evidence | 0.0% |
| preference_evidence | 0.0% |
| user_evidence | 0.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_evidence_recall | 0.000 |
| avg_top1_relevance | 0.000 |
| perfect_recall_rate | 0.000 |
| recall_abstention_evidence | 0.000 |
| recall_assistant_facts_evidence | 0.000 |
| recall_implicit_connection_evidence | 0.000 |
| recall_preference_evidence | 0.000 |
| recall_user_evidence | 0.000 |
| zero_recall_rate | 1.000 |

## Error Analysis

Total errors: 250 / 250

### convomem_assistant_facts_evidence_100_q (assistant_facts_evidence)
- **Q**: I'm finally getting around to that productivity hack you mentioned last week. Can you remind me of the specific automation tool and method you suggested for integrating my color-coded spreadsheet with our company's Salesforce CRM?
- **Expected**: I suggested using Zapier to create an automation. The method involves setting up a 'Zap' where the trigger is a 'New or Updated Spreadsheet Row' in your sheet, and the action is to 'Create or Update a Record' in Salesforce, mapping your spreadsheet columns to the corresponding Salesforce fields.
- **Generated**: 

### convomem_assistant_facts_evidence_101_q (assistant_facts_evidence)
- **Q**: Can you remind me of the specific opening line you suggested for my SaaS cold calls?
- **Expected**: Hi [Prospect Name], this is Alex from InnovateLeads. The reason I'm calling is that I noticed your company is in a high-growth phase, and firms like yours often find our lead-gen tools can help scale without increasing headcount.
- **Generated**: 

### convomem_assistant_facts_evidence_102_q (assistant_facts_evidence)
- **Q**: Can you remind me of the three-step framework you suggested for handling pricing objections?
- **Expected**: The three-step framework for handling pricing objections is: Acknowledge, Reframe, Justify.
- **Generated**: 

### convomem_assistant_facts_evidence_103_q (assistant_facts_evidence)
- **Q**: I'm drafting another follow-up for a lead that's gone cold. You gave me a great subject line for this situation before, one that was short and had a high open rate. What was it again?
- **Expected**: The subject line I recommended was 'Quick question about our last chat'.
- **Generated**: 

### convomem_assistant_facts_evidence_104_q (assistant_facts_evidence)
- **Q**: Can you remind me of the humming exercise you recommended for vocal warm-ups?
- **Expected**: You should hum scales to warm up your voice before calls.
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
