# Hippocampus Evaluation Report: LoCoMo

**Date**: 2026-04-19T09:40:42.821622+00:00
**Mode**: consolidated
**Model (judge)**: openai/Kimi-K2.5
**Thinking**: enabled
**Temperature**: 1.0
**Top-p**: 0.95
**Search top_k**: 10
**Concurrency**: 2
**Scenarios**: 3

## Consolidation

| Metric | Value |
|--------|-------|
| Processed | 258 |
| Succeeded | 258 |
| Failed | 0 |

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 497 |
| Correct | 192 |
| **Accuracy** | **38.6%** |
| Avg Latency | 106.2ms |
| Est. Total Time | 52.8s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 67.0% |
| multi_hop | 6.7% |
| open_ended | 37.0% |
| single_hop | 40.5% |
| temporal | 33.3% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.522 |

## Error Analysis

Total errors: 305 / 497

### locomo_0_q0 (multi_hop)
- **Q**: When did Caroline go to the LGBTQ support group?
- **Expected**: 7 May 2023
- **Generated**: Yesterday

### locomo_0_q5 (multi_hop)
- **Q**: When did Melanie run a charity race?
- **Expected**: The sunday before 25 May 2023
- **Generated**: Last Saturday

### locomo_0_q6 (multi_hop)
- **Q**: When is Melanie planning on going camping?
- **Expected**: June 2023
- **Generated**: Next month.

### locomo_0_q8 (multi_hop)
- **Q**: When did Caroline give a speech at a school?
- **Expected**: The week before 9 June 2023
- **Generated**: I don't know.

### locomo_0_q9 (multi_hop)
- **Q**: When did Caroline meet up with her friends, family, and mentors?
- **Expected**: The week before 9 June 2023
- **Generated**: I don't know.

## Configuration

```json
{
  "llm_model": "openai/Kimi-K2.5",
  "llm_thinking": true,
  "llm_temperature": 1.0,
  "llm_top_p": 0.95,
  "mode": "consolidated",
  "search_top_k": 10,
  "concurrency": 2,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 2.0,
  "num_scenarios": 3,
  "consolidation": {
    "processed": 258,
    "succeeded": 258,
    "failed": 0
  }
}
```
