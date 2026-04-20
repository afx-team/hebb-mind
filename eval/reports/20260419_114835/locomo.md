# Hippocampus Evaluation Report: LoCoMo

**Date**: 2026-04-19T12:53:56.533896+00:00
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
| Processed | 234 |
| Succeeded | 234 |
| Failed | 0 |

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 497 |
| Correct | 187 |
| **Accuracy** | **37.6%** |
| Avg Latency | 101.7ms |
| Est. Total Time | 50.5s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 66.1% |
| multi_hop | 5.6% |
| open_ended | 35.5% |
| single_hop | 41.9% |
| temporal | 28.6% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.520 |

## Error Analysis

Total errors: 310 / 497

### locomo_0_q0 (multi_hop)
- **Q**: When did Caroline go to the LGBTQ support group?
- **Expected**: 7 May 2023
- **Generated**: Yesterday

### locomo_0_q1 (multi_hop)
- **Q**: When did Melanie paint a sunrise?
- **Expected**: 2022
- **Generated**: Last year.

### locomo_0_q3 (single_hop)
- **Q**: What did Caroline research?
- **Expected**: Adoption agencies
- **Generated**: I don't know.

### locomo_0_q5 (multi_hop)
- **Q**: When did Melanie run a charity race?
- **Expected**: The sunday before 25 May 2023
- **Generated**: Last Saturday

### locomo_0_q6 (multi_hop)
- **Q**: When is Melanie planning on going camping?
- **Expected**: June 2023
- **Generated**: Next month.

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
    "processed": 234,
    "succeeded": 234,
    "failed": 0
  }
}
```
