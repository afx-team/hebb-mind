# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 4
**Scenarios**: 1496

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1496 |
| Correct | 1340 |
| **Accuracy** | **89.6%** |
| Avg Latency | 1386.5ms |
| Est. Total Time | 34.6min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| highlevel_rec | 89.6% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.307 |
| hit@1 | 0.489 |
| hit@10 | 0.991 |
| hit@3 | 0.783 |
| hit@5 | 0.896 |

## Error Analysis

Total errors: 156 / 1496

### membench_highlevel_rec_movie_1_1_q (highlevel_rec)
- **Q**: According to the movies I mentioned, what kind of movies might I prefer to watch?
- **Expected**: Drama
- **Generated**: 

### membench_highlevel_rec_movie_15_15_q (highlevel_rec)
- **Q**: According to the movies I mentioned, what kind of movies might I prefer to watch?
- **Expected**: Action
- **Generated**: 

### membench_highlevel_rec_movie_19_19_q (highlevel_rec)
- **Q**: According to the movies I mentioned, what kind of movies might I prefer to watch?
- **Expected**: Action
- **Generated**: 

### membench_highlevel_rec_movie_27_27_q (highlevel_rec)
- **Q**: According to the movies I mentioned, what kind of movies might I prefer to watch?
- **Expected**: Drama
- **Generated**: 

### membench_highlevel_rec_movie_28_28_q (highlevel_rec)
- **Q**: According to the movies I mentioned, what kind of movies might I prefer to watch?
- **Expected**: Action
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
  "num_scenarios": 1496,
  "per_category_hit_at_k": {
    "highlevel_rec": {
      "hit@1": 0.4893048128342246,
      "hit@10": 0.9913101604278075,
      "hit@3": 0.7827540106951871,
      "hit@5": 0.8957219251336899,
      "n": 1496.0
    }
  }
}
```
