# Hebb Mind Evaluation Report: LoCoMo (end-to-end QA)

**Eval version**: v1
**Mode**: raw_production_mirror
**Model (judge)**: openai/DeepSeek-V4-Pro
**Thinking**: disabled
**Temperature**: 1.0
**Top-p**: 0.95
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 10

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1978 |
| Correct | 1526 |
| **Accuracy** | **77.1%** |
| Avg Latency | 7761.5ms |
| Est. Total Time | 255.9min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 88.3% |
| multi_hop | 64.5% |
| open_ended | 84.9% |
| single_hop | 64.4% |
| temporal | 33.7% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_judge_confidence | 0.943 |
| avg_recall_at_k | 0.917 |
| avg_retrieval_latency_ms | 4646.724 |
| avg_top1_relevance | 0.602 |
| no_evidence_excluded | 8.000 |
| session_recall_at_k | 0.958 |

## Error Analysis

Total errors: 456 / 1978

### locomo_0_q0 (multi_hop)
- **Q**: When did Caroline go to the LGBTQ support group?
- **Expected**: 7 May 2023
- **Generated**: 

### locomo_0_q7 (single_hop)
- **Q**: What is Caroline's relationship status?
- **Expected**: Single
- **Generated**: I don't know.

### locomo_0_q23 (single_hop)
- **Q**: What books has Melanie read?
- **Expected**: "Nothing is Impossible", "Charlotte's Web"
- **Generated**: Charlotte's Web

### locomo_0_q26 (multi_hop)
- **Q**: When did Melanie read the book "nothing is impossible"?
- **Expected**: 2022
- **Generated**: I don't know.

### locomo_0_q30 (temporal)
- **Q**: Would Melanie be considered a member of the LGBTQ community?
- **Expected**: Likely no, she does not refer to herself as part of it
- **Generated**: I don't know.

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
  "llm_model": "openai/DeepSeek-V4-Pro",
  "llm_thinking": false,
  "llm_temperature": 1.0,
  "llm_top_p": 0.95,
  "num_scenarios": 10,
  "adversarial_excluded": 8
}
```
