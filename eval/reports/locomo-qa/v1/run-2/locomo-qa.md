# Hebb Mind Evaluation Report: LoCoMo (end-to-end QA)

**Eval version**: v1
**Mode**: raw_production_mirror
**Model (judge)**: openai/Kimi-K2.5
**Thinking**: enabled
**Temperature**: 1.0
**Top-p**: 0.95
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 10

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1978 |
| Correct | 1503 |
| **Accuracy** | **76.0%** |
| Avg Latency | 14005.3ms |
| Est. Total Time | 461.7min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 95.1% |
| multi_hop | 63.9% |
| open_ended | 83.6% |
| single_hop | 51.6% |
| temporal | 29.2% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_judge_confidence | 0.966 |
| avg_recall_at_k | 0.852 |
| avg_retrieval_latency_ms | 288.217 |
| avg_top1_relevance | 0.333 |
| no_evidence_excluded | 8.000 |
| session_recall_at_k | 0.904 |

## Error Analysis

Total errors: 477 / 1978

### locomo_0_q7 (single_hop)
- **Q**: What is Caroline's relationship status?
- **Expected**: Single
- **Generated**: I don't know.

### locomo_0_q8 (multi_hop)
- **Q**: When did Caroline give a speech at a school?
- **Expected**: The week before 9 June 2023
- **Generated**: I don't know.

### locomo_0_q10 (multi_hop)
- **Q**: How long has Caroline had her current group of friends for?
- **Expected**: 4 years
- **Generated**: I don't know.

### locomo_0_q11 (single_hop)
- **Q**: Where did Caroline move from 4 years ago?
- **Expected**: Sweden
- **Generated**: home country

### locomo_0_q15 (single_hop)
- **Q**: What activities does Melanie partake in?
- **Expected**: pottery, camping, painting, swimming
- **Generated**: Camping, hiking in the mountains, exploring forests

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_production_mirror",
  "metric": "end_to_end_qa_accuracy",
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
  "llm_top_p": 0.95,
  "num_scenarios": 10,
  "adversarial_excluded": 8
}
```
