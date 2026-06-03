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
| Correct | 994 |
| **Accuracy** | **99.4%** |
| Avg Latency | 2252.5ms |
| Est. Total Time | 37.5min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| simple | 99.4% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.766 |
| hit@1 | 0.913 |
| hit@10 | 1.000 |
| hit@3 | 0.980 |
| hit@5 | 0.994 |

## Error Analysis

Total errors: 6 / 1000

### membench_simple_roles_206_206_q (simple)
- **Q**: What is the hometown of my female cousin?
- **Expected**: San Antonio, TX
- **Generated**: 

### membench_simple_roles_451_451_q (simple)
- **Q**: What is my male cousin's position?
- **Expected**: High School Math Teacher
- **Generated**: 

### membench_simple_events_88_588_q (simple)
- **Q**: What is the scale of Bilingual Biz?
- **Expected**: one hundred people
- **Generated**: 

### membench_simple_events_99_599_q (simple)
- **Q**: What is the scale of CineArtFest?
- **Expected**: three hundred people
- **Generated**: 

### membench_simple_events_251_751_q (simple)
- **Q**: What is the scale of TasteArt Fest?
- **Expected**: three thousand people
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
  "num_scenarios": 1000,
  "per_category_hit_at_k": {
    "simple": {
      "hit@1": 0.913,
      "hit@10": 1.0,
      "hit@3": 0.98,
      "hit@5": 0.994,
      "n": 1000.0
    }
  }
}
```
