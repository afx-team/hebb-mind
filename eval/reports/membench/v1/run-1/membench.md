# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 4
**Scenarios**: 5

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 5 |
| Correct | 5 |
| **Accuracy** | **100.0%** |
| Avg Latency | 52.3ms |
| Est. Total Time | 0.3s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| noisy | 100.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.333 |
| hit@1 | 0.600 |
| hit@10 | 1.000 |
| hit@3 | 1.000 |
| hit@5 | 1.000 |

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_per_turn_pair",
  "metric": "turn_level_hit_at_k",
  "search_top_k": 5,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 5
}
```
