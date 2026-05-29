# Hebb Mind Evaluation Report: LoCoMo

**Eval version**: v4
**Mode**: raw_production_mirror
**Model (judge)**: openai/DeepSeek-V4-Pro
**Thinking**: disabled
**Temperature**: 1.0
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 10

## Consolidation

| Metric | Value |
|--------|-------|
| Processed | 1065 |
| Succeeded | 1065 |
| Failed | 0 |

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1978 |
| Correct | 1738 |
| **Accuracy** | **87.9%** |
| Avg Latency | 2734.0ms |
| Est. Total Time | 90.1min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| adversarial | 77.8% |
| multi_hop | 90.3% |
| open_ended | 89.5% |
| single_hop | 96.8% |
| temporal | 85.4% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_recall_at_k | 0.841 |
| avg_retrieval_latency_ms | 831.283 |
| avg_top1_relevance | 0.684 |
| no_evidence_excluded | 8.000 |
| qa_accuracy | 0.576 |
| qa_accuracy_adversarial | 0.942 |
| qa_accuracy_multi_hop | 0.162 |
| qa_accuracy_open_ended | 0.567 |
| qa_accuracy_single_hop | 0.555 |
| qa_accuracy_temporal | 0.393 |
| qa_correct | 1140.000 |

## Error Analysis

Total errors: 240 / 1978

### locomo_0_q4 (single_hop)
- **Q**: What is Caroline's identity?
- **Expected**: Transgender woman
- **Generated**: Transgender woman.

### locomo_0_q26 (multi_hop)
- **Q**: When did Melanie read the book "nothing is impossible"?
- **Expected**: 2022
- **Generated**: I don't know.

### locomo_0_q50 (temporal)
- **Q**: What would Caroline's political leaning likely be?
- **Expected**: Liberal
- **Generated**: Liberal or progressive

### locomo_0_q94 (open_ended)
- **Q**: What is Melanie's hand-painted bowl a reminder of?
- **Expected**: art and self-expression
- **Generated**: I don't know.

### locomo_0_q100 (open_ended)
- **Q**: What kind of place does Caroline want to create for people?
- **Expected**: a safe and inviting place for people to grow
- **Generated**: I don't know.

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
  "llm_model": "openai/DeepSeek-V4-Pro",
  "llm_thinking": false,
  "llm_temperature": 1.0,
  "num_scenarios": 10,
  "adversarial_excluded": 8,
  "consolidation": {
    "processed": 1065,
    "succeeded": 1065,
    "failed": 0,
    "errors": []
  }
}
```
