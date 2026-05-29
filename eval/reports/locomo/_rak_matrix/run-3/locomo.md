# Hebb Mind Evaluation Report: LoCoMo

**Eval version**: v4
**Mode**: raw_production_mirror
**Model (judge)**: openai/Kimi-K2.5
**Thinking**: enabled
**Temperature**: 1.0
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 10

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1978 |
| Correct | 1820 |
| **Accuracy** | **92.0%** |
| Avg Latency | 1057.1ms |
| Est. Total Time | 34.8min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 93.9% |
| multi_hop | 88.2% |
| open_ended | 96.3% |
| single_hop | 88.3% |
| temporal | 67.4% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_recall_at_k | 0.870 |
| avg_retrieval_latency_ms | 1057.012 |
| avg_top1_relevance | 0.327 |
| no_evidence_excluded | 8.000 |
| qa_accuracy | 0.000 |
| qa_accuracy_adversarial | 0.000 |
| qa_accuracy_multi_hop | 0.000 |
| qa_accuracy_open_ended | 0.000 |
| qa_accuracy_single_hop | 0.000 |
| qa_accuracy_temporal | 0.000 |
| qa_correct | 0.000 |

## Error Analysis

Total errors: 158 / 1978

### locomo_0_q2 (temporal)
- **Q**: What fields would Caroline be likely to pursue in her educaton?
- **Expected**: Psychology, counseling certification
- **Generated**: 

### locomo_0_q4 (single_hop)
- **Q**: What is Caroline's identity?
- **Expected**: Transgender woman
- **Generated**: 

### locomo_0_q8 (multi_hop)
- **Q**: When did Caroline give a speech at a school?
- **Expected**: The week before 9 June 2023
- **Generated**: 

### locomo_0_q10 (multi_hop)
- **Q**: How long has Caroline had her current group of friends for?
- **Expected**: 4 years
- **Generated**: 

### locomo_0_q15 (single_hop)
- **Q**: What activities does Melanie partake in?
- **Expected**: pottery, camping, painting, swimming
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
  "llm_model": "openai/Kimi-K2.5",
  "llm_thinking": true,
  "llm_temperature": 1.0,
  "num_scenarios": 10,
  "adversarial_excluded": 8
}
```
