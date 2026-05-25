# Hebb Mind Evaluation Report: LongMemEval

**Date**: 2026-04-19T10:12:22.473601+00:00
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
| Total Questions | 3 |
| Correct | 2 |
| **Accuracy** | **66.7%** |
| Avg Latency | 142.9ms |
| Est. Total Time | 0.4s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| single-session-user | 66.7% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.536 |

## Error Analysis

Total errors: 1 / 3

### longmemeval_51a45a95 (single-session-user)
- **Q**: Where did I redeem a $5 coupon on coffee creamer?
- **Expected**: Target
- **Generated**: I don't know. The memories mention that you found the $5 coffee creamer coupon in your email inbox and redeemed it last Sunday, but they don't specify which store you redeemed it at.

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
