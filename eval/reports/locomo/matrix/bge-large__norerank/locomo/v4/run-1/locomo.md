# Hebb Mind Evaluation Report: LoCoMo

**Eval version**: v4
**Mode**: raw_production_mirror
**Model (judge)**: DeepSeek-V4-Pro
**Thinking**: disabled
**Temperature**: 1.0
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 10

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1978 |
| Correct | 1862 |
| **Accuracy** | **94.1%** |
| Avg Latency | 1157.5ms |
| Est. Total Time | 38.2min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 95.1% |
| multi_hop | 93.1% |
| open_ended | 97.1% |
| single_hop | 89.3% |
| temporal | 79.8% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_recall_at_k | 0.899 |
| avg_retrieval_latency_ms | 1157.434 |
| avg_top1_relevance | 0.635 |
| no_evidence_excluded | 8.000 |
| qa_accuracy | 0.000 |
| qa_accuracy_adversarial | 0.000 |
| qa_accuracy_multi_hop | 0.000 |
| qa_accuracy_open_ended | 0.000 |
| qa_accuracy_single_hop | 0.000 |
| qa_accuracy_temporal | 0.000 |
| qa_correct | 0.000 |

## Error Analysis

Total errors: 116 / 1978

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
  "eval_version": "v4",
  "mode": "raw_production_mirror",
  "metric": "session_evidence_recall+end_to_end_qa",
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "prev_turns": 2,
  "next_turns": 2,
  "llm_model": "DeepSeek-V4-Pro",
  "llm_thinking": false,
  "llm_temperature": 1.0,
  "num_scenarios": 10,
  "adversarial_excluded": 8
}
```
