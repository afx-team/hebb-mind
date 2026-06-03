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
| Correct | 991 |
| **Accuracy** | **99.1%** |
| Avg Latency | 2069.1ms |
| Est. Total Time | 34.5min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| aggregative | 99.1% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.113 |
| hit@1 | 0.916 |
| hit@10 | 0.999 |
| hit@3 | 0.980 |
| hit@5 | 0.991 |

## Error Analysis

Total errors: 9 / 1000

### membench_aggregative_roles_227_227_q (aggregative)
- **Q**: How many people have birthdays in the first half of the year?
- **Expected**: 4 people
- **Generated**: 

### membench_aggregative_events_18_518_q (aggregative)
- **Q**: How many events are taking place in Chicago?
- **Expected**: 9 events
- **Generated**: 

### membench_aggregative_events_223_723_q (aggregative)
- **Q**: How many events are taking place in Los Angeles?
- **Expected**: 9 events
- **Generated**: 

### membench_aggregative_events_229_729_q (aggregative)
- **Q**: How many events take place in Seattle?
- **Expected**: 8 events
- **Generated**: 

### membench_aggregative_events_300_800_q (aggregative)
- **Q**: How many events are taking place in Seattle?
- **Expected**: 8 events
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
    "aggregative": {
      "hit@1": 0.916,
      "hit@10": 0.999,
      "hit@3": 0.98,
      "hit@5": 0.991,
      "n": 1000.0
    }
  }
}
```
