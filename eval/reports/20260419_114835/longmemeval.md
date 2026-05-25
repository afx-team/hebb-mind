# Hebb Mind Evaluation Report: LongMemEval

**Date**: 2026-04-19T13:05:54.155725+00:00
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
| Processed | 267 |
| Succeeded | 267 |
| Failed | 0 |

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 3 |
| Correct | 1 |
| **Accuracy** | **33.3%** |
| Avg Latency | 73.8ms |
| Est. Total Time | 0.2s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| single-session-user | 33.3% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.487 |

## Error Analysis

Total errors: 2 / 3

### longmemeval_118b2229 (single-session-user)
- **Q**: How long is my daily commute to work?
- **Expected**: 45 minutes each way
- **Generated**: I don't know.

### longmemeval_51a45a95 (single-session-user)
- **Q**: Where did I redeem a $5 coupon on coffee creamer?
- **Expected**: Target
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
    "processed": 267,
    "succeeded": 267,
    "failed": 0
  }
}
```
