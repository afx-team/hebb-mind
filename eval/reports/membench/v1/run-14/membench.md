# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 4
**Scenarios**: 1000

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1000 |
| Correct | 860 |
| **Accuracy** | **86.0%** |
| Avg Latency | 1255.1ms |
| Est. Total Time | 20.9min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| conditional | 86.0% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.420 |
| hit@1 | 0.530 |
| hit@10 | 0.959 |
| hit@3 | 0.755 |
| hit@5 | 0.860 |

## Error Analysis

Total errors: 140 / 1000

### membench_conditional_roles_0_0_q (conditional)
- **Q**: What is the age of someone with an Associate Degree?
- **Expected**: 28 years old
- **Generated**: 

### membench_conditional_roles_5_5_q (conditional)
- **Q**: What kind of education does someone with the occupation of a lawyer have?
- **Expected**: Bachelor
- **Generated**: 

### membench_conditional_roles_8_8_q (conditional)
- **Q**: What is the height of someone from Austin, TX?
- **Expected**: 158cm
- **Generated**: 

### membench_conditional_roles_10_10_q (conditional)
- **Q**: What is the education of someone whose hometown is Denver, CO?
- **Expected**: Master
- **Generated**: 

### membench_conditional_roles_14_14_q (conditional)
- **Q**: What is the occupation of someone whose hometown is Austin, TX?
- **Expected**: Salesperson
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
  "num_scenarios": 1000,
  "per_category_hit_at_k": {
    "conditional": {
      "hit@1": 0.53,
      "hit@10": 0.959,
      "hit@3": 0.755,
      "hit@5": 0.86,
      "n": 1000.0
    }
  }
}
```
