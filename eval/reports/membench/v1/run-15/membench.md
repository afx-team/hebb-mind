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
| Correct | 1495 |
| **Accuracy** | **99.7%** |
| Avg Latency | 1503.6ms |
| Est. Total Time | 37.6min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| highlevel | 99.7% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.134 |
| hit@1 | 0.611 |
| hit@10 | 1.000 |
| hit@3 | 0.961 |
| hit@5 | 0.997 |

## Error Analysis

Total errors: 5 / 1500

### membench_highlevel_food_130_630_q (highlevel)
- **Q**: According to the dishes I mentioned, Which flavor I might prefer?
- **Expected**: Numbing
- **Generated**: 

### membench_highlevel_book_3_1003_q (highlevel)
- **Q**: Accodring to the books I mentioned, What kind of books do I probably prefer to read?
- **Expected**: Performing Arts
- **Generated**: 

### membench_highlevel_book_45_1045_q (highlevel)
- **Q**: Accodring to the books I mentioned, What kind of books do I probably prefer to read?
- **Expected**: Performing Arts
- **Generated**: 

### membench_highlevel_book_76_1076_q (highlevel)
- **Q**: Accodring to the books I mentioned, What kind of books do I probably prefer to read?
- **Expected**: Art
- **Generated**: 

### membench_highlevel_book_360_1360_q (highlevel)
- **Q**: Accodring to the books I mentioned, What kind of books do I probably prefer to read?
- **Expected**: Poetry
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
    "highlevel": {
      "hit@1": 0.6106666666666667,
      "hit@10": 1.0,
      "hit@3": 0.9606666666666667,
      "hit@5": 0.9966666666666667,
      "n": 1500.0
    }
  }
}
```
