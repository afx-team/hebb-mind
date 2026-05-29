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
| Correct | 1894 |
| **Accuracy** | **95.8%** |
| Avg Latency | 1792.1ms |
| Est. Total Time | 59.1min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 97.3% |
| multi_hop | 94.1% |
| open_ended | 98.2% |
| single_hop | 92.9% |
| temporal | 79.8% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_recall_at_k | 0.917 |
| avg_retrieval_latency_ms | 1792.014 |
| avg_top1_relevance | 0.602 |
| no_evidence_excluded | 8.000 |
| qa_accuracy | 0.000 |
| qa_accuracy_adversarial | 0.000 |
| qa_accuracy_multi_hop | 0.000 |
| qa_accuracy_open_ended | 0.000 |
| qa_accuracy_single_hop | 0.000 |
| qa_accuracy_temporal | 0.000 |
| qa_correct | 0.000 |

## Error Analysis

Total errors: 84 / 1978

### locomo_0_q34 (single_hop)
- **Q**: What events has Caroline participated in to help children?
- **Expected**: Mentoring program, school speech
- **Generated**: 

### locomo_0_q42 (temporal)
- **Q**: Would Melanie be more interested in going to a national park or a theme park?
- **Expected**: National park; she likes the outdoors
- **Generated**: 

### locomo_0_q44 (multi_hop)
- **Q**: When is Melanie's daughter's birthday?
- **Expected**: 13 August
- **Generated**: 

### locomo_0_q47 (single_hop)
- **Q**: Who supports Caroline when she has a negative experience?
- **Expected**: Her mentors, family, and friends
- **Generated**: 

### locomo_0_q49 (multi_hop)
- **Q**: When did Caroline and Melanie go to a pride fesetival together?
- **Expected**: 2022
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
