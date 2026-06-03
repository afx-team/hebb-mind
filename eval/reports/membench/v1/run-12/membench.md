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
| Correct | 903 |
| **Accuracy** | **90.3%** |
| Avg Latency | 2624.5ms |
| Est. Total Time | 43.7min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| post_processing | 90.3% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.459 |
| hit@1 | 0.601 |
| hit@10 | 0.972 |
| hit@3 | 0.836 |
| hit@5 | 0.903 |

## Error Analysis

Total errors: 97 / 1000

### membench_post_processing_roles_13_13_q (post_processing)
- **Q**: What is the email address suffix for someone who works as a Professor?
- **Expected**: @innovativelearningtech.com
- **Generated**: 

### membench_post_processing_roles_26_26_q (post_processing)
- **Q**: What are the main responsibilities of a 31-year-old in their profession?
- **Expected**: Conduct studies and experiments to gain new knowledge and develop solutions in specific fields
- **Generated**: 

### membench_post_processing_roles_28_28_q (post_processing)
- **Q**: What is the primary responsibility of a 32-year-old in their job?
- **Expected**: Provide financial planning and investment advice
- **Generated**: 

### membench_post_processing_roles_30_30_q (post_processing)
- **Q**: In which season does a person with a PhD celebrate their birthday?
- **Expected**: Spring
- **Generated**: 

### membench_post_processing_roles_86_86_q (post_processing)
- **Q**: For someone who works in New York, NY, which of the following options would best describe their workplace?
- **Expected**: The largest city in the U.S., known for its iconic skyline and diverse culture.
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
    "post_processing": {
      "hit@1": 0.601,
      "hit@10": 0.972,
      "hit@3": 0.836,
      "hit@5": 0.903,
      "n": 1000.0
    }
  }
}
```
