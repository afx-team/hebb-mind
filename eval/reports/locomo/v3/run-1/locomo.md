# Hebb Mind Evaluation Report: LoCoMo

**Eval version**: v3
**Mode**: raw_production_mirror
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 10

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1978 |
| Correct | 1774 |
| **Accuracy** | **89.7%** |
| Avg Latency | 1251.5ms |
| Est. Total Time | 41.3min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 89.9% |
| multi_hop | 90.0% |
| open_ended | 91.9% |
| single_hop | 87.2% |
| temporal | 74.2% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_recall_at_k | 0.846 |
| avg_top1_relevance | 0.629 |
| no_evidence_excluded | 8.000 |

## Error Analysis

Total errors: 204 / 1978

### locomo_0_q4 (single_hop)
- **Q**: What is Caroline's identity?
- **Expected**: Transgender woman
- **Generated**: 

### locomo_0_q7 (single_hop)
- **Q**: What is Caroline's relationship status?
- **Expected**: Single
- **Generated**: 

### locomo_0_q15 (single_hop)
- **Q**: What activities does Melanie partake in?
- **Expected**: pottery, camping, painting, swimming
- **Generated**: 

### locomo_0_q18 (single_hop)
- **Q**: Where has Melanie camped?
- **Expected**: beach, mountains, forest
- **Generated**: 

### locomo_0_q27 (temporal)
- **Q**: Would Caroline pursue writing as a career option?
- **Expected**: LIkely no; though she likes reading, she wants to be a counselor
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v3",
  "mode": "raw_production_mirror",
  "metric": "session_evidence_recall",
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 10,
  "adversarial_excluded": 8
}
```
