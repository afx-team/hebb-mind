# Hippocampus Evaluation Report: LoCoMo

**Date**: 2026-04-19T02:12:59.971936+00:00
**Mode**: raw
**Model (judge)**: openai/Kimi-K2.5
**Thinking**: enabled
**Temperature**: 1.0
**Top-p**: 0.95
**Search top_k**: 10
**Concurrency**: 2
**Scenarios**: 3

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 497 |
| Correct | 254 |
| **Accuracy** | **51.1%** |
| Avg Latency | 144.1ms |
| Est. Total Time | 1.2min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 63.4% |
| multi_hop | 24.4% |
| open_ended | 61.0% |
| single_hop | 43.2% |
| temporal | 33.3% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.525 |

## Error Analysis

Total errors: 243 / 497

### locomo_0_q0 (multi_hop)
- **Q**: When did Caroline go to the LGBTQ support group?
- **Expected**: 7 May 2023
- **Generated**: Yesterday (Session 1).

### locomo_0_q2 (temporal)
- **Q**: What fields would Caroline be likely to pursue in her educaton?
- **Expected**: Psychology, counseling certification
- **Generated**: I don't know.

### locomo_0_q5 (multi_hop)
- **Q**: When did Melanie run a charity race?
- **Expected**: The sunday before 25 May 2023
- **Generated**: Last Saturday (mentioned in Session 2).

### locomo_0_q6 (multi_hop)
- **Q**: When is Melanie planning on going camping?
- **Expected**: June 2023
- **Generated**: Next month.

### locomo_0_q7 (single_hop)
- **Q**: What is Caroline's relationship status?
- **Expected**: Single
- **Generated**: I don't know.

## Configuration

```json
{
  "llm_model": "openai/Kimi-K2.5",
  "llm_thinking": true,
  "llm_temperature": 1.0,
  "llm_top_p": 0.95,
  "mode": "raw",
  "search_top_k": 10,
  "concurrency": 2,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 2.0,
  "num_scenarios": 3
}
```
