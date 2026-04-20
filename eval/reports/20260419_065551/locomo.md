# Hippocampus Evaluation Report: LoCoMo

**Date**: 2026-04-19T11:22:43.224532+00:00
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
| Processed | 519 |
| Succeeded | 0 |
| Failed | 519 |

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 497 |
| Correct | 77 |
| **Accuracy** | **15.5%** |
| Avg Latency | 125.2ms |
| Est. Total Time | 1.0min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 67.9% |
| multi_hop | 0.0% |
| open_ended | 0.0% |
| single_hop | 0.0% |
| temporal | 4.8% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.457 |

## Error Analysis

Total errors: 420 / 497

### locomo_0_q0 (multi_hop)
- **Q**: When did Caroline go to the LGBTQ support group?
- **Expected**: 7 May 2023
- **Generated**: I don't know.

### locomo_0_q1 (multi_hop)
- **Q**: When did Melanie paint a sunrise?
- **Expected**: 2022
- **Generated**: I don't know.

### locomo_0_q2 (temporal)
- **Q**: What fields would Caroline be likely to pursue in her educaton?
- **Expected**: Psychology, counseling certification
- **Generated**: I don't know.

### locomo_0_q3 (single_hop)
- **Q**: What did Caroline research?
- **Expected**: Adoption agencies
- **Generated**: I don't know.

### locomo_0_q4 (single_hop)
- **Q**: What is Caroline's identity?
- **Expected**: Transgender woman
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
    "processed": 519,
    "succeeded": 0,
    "failed": 519
  }
}
```
