# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 8
**Scenarios**: 1000

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1000 |
| Correct | 1000 |
| **Accuracy** | **100.0%** |
| Avg Latency | 2321.2ms |
| Est. Total Time | 38.7min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| comparative | 100.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.811 |
| hit@1 | 0.898 |
| hit@10 | 1.000 |
| hit@3 | 0.996 |
| hit@5 | 1.000 |

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_per_turn_pair",
  "metric": "turn_level_hit_at_k",
  "search_top_k": 5,
  "concurrency": 8,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 1000,
  "per_category_hit_at_k": {
    "comparative": {
      "hit@1": 0.898,
      "hit@10": 1.0,
      "hit@3": 0.996,
      "hit@5": 1.0,
      "n": 1000.0
    }
  }
}
```
