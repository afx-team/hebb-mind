# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 4
**Scenarios**: 1500

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1500 |
| Correct | 1498 |
| **Accuracy** | **99.9%** |
| Avg Latency | 1095.0ms |
| Est. Total Time | 27.4min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| lowlevel_rec | 99.9% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.085 |
| hit@1 | 0.893 |
| hit@10 | 1.000 |
| hit@3 | 0.983 |
| hit@5 | 0.999 |

## Error Analysis

Total errors: 2 / 1500

### membench_lowlevel_rec_movie_214_214_q (lowlevel_rec)
- **Q**: What movies have you recommended to me before?
- **Expected**: ['Aristocats, The (1970)']
- **Generated**: 

### membench_lowlevel_rec_book_432_1432_q (lowlevel_rec)
- **Q**: What books have you recommended to me before?
- **Expected**: ['Das Hotel New Hampshire']
- **Generated**: 

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
  "num_scenarios": 1500,
  "per_category_hit_at_k": {
    "lowlevel_rec": {
      "hit@1": 0.8926666666666667,
      "hit@10": 1.0,
      "hit@3": 0.9833333333333333,
      "hit@5": 0.9986666666666667,
      "n": 1500.0
    }
  }
}
```
