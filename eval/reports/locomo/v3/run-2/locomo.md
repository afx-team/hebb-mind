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
| Correct | 1846 |
| **Accuracy** | **93.3%** |
| Avg Latency | 1429.5ms |
| Est. Total Time | 47.1min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 93.3% |
| multi_hop | 91.6% |
| open_ended | 96.8% |
| single_hop | 89.3% |
| temporal | 79.8% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_recall_at_k | 0.889 |
| avg_top1_relevance | 0.644 |
| no_evidence_excluded | 8.000 |

## Error Analysis

Total errors: 132 / 1978

### locomo_0_q15 (single_hop)
- **Q**: What activities does Melanie partake in?
- **Expected**: pottery, camping, painting, swimming
- **Generated**: 

### locomo_0_q34 (single_hop)
- **Q**: What events has Caroline participated in to help children?
- **Expected**: Mentoring program, school speech
- **Generated**: 

### locomo_0_q42 (temporal)
- **Q**: Would Melanie be more interested in going to a national park or a theme park?
- **Expected**: National park; she likes the outdoors
- **Generated**: 

### locomo_0_q47 (single_hop)
- **Q**: Who supports Caroline when she has a negative experience?
- **Expected**: Her mentors, family, and friends
- **Generated**: 

### locomo_0_q73 (multi_hop)
- **Q**: When did Melanie get hurt?
- **Expected**: September 2023
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
