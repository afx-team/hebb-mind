# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 8
**Scenarios**: 500

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 500 |
| Correct | 499 |
| **Accuracy** | **99.8%** |
| Avg Latency | 1909.6ms |
| Est. Total Time | 15.9min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| RecMultiSession | 99.8% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.026 |
| hit@1 | 0.608 |
| hit@10 | 1.000 |
| hit@3 | 0.944 |
| hit@5 | 0.998 |

## Error Analysis

Total errors: 1 / 500

### membench_RecMultiSession_multi_agent_490_490_q (RecMultiSession)
- **Q**: What movies, books and dishes have you recommended to me?
- **Expected**: ['Air Force One (1997)', 'Salted Peanut Butter Cookies', 'Chocolate Dipped Bacon', 'Hamlet (Bantam Classics)']
- **Generated**: 

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
  "num_scenarios": 500,
  "per_category_hit_at_k": {
    "RecMultiSession": {
      "hit@1": 0.608,
      "hit@10": 1.0,
      "hit@3": 0.944,
      "hit@5": 0.998,
      "n": 500.0
    }
  }
}
```
