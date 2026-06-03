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
| Correct | 971 |
| **Accuracy** | **97.1%** |
| Avg Latency | 2380.6ms |
| Est. Total Time | 39.7min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| knowledge_update | 97.1% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.862 |
| hit@1 | 0.542 |
| hit@10 | 0.996 |
| hit@3 | 0.931 |
| hit@5 | 0.971 |

## Error Analysis

Total errors: 29 / 1000

### membench_knowledge_update_roles_7_7_q (knowledge_update)
- **Q**: What does my sister do for a living?
- **Expected**: Engineer
- **Generated**: 

### membench_knowledge_update_roles_50_50_q (knowledge_update)
- **Q**: What is the occupation of my nephew?
- **Expected**: Courier
- **Generated**: 

### membench_knowledge_update_roles_54_54_q (knowledge_update)
- **Q**: What is the occupation of the boss?
- **Expected**: Scientist
- **Generated**: 

### membench_knowledge_update_roles_92_92_q (knowledge_update)
- **Q**: What does my sister do for a living?
- **Expected**: Electrician
- **Generated**: 

### membench_knowledge_update_roles_104_104_q (knowledge_update)
- **Q**: What is my female cousin's position?
- **Expected**: Concert Musician
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
    "knowledge_update": {
      "hit@1": 0.542,
      "hit@10": 0.996,
      "hit@3": 0.931,
      "hit@5": 0.971,
      "n": 1000.0
    }
  }
}
```
